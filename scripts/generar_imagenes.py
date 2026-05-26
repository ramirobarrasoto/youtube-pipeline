"""
Generación / descarga de imágenes para los videos.

Estrategia (en orden):
  1. Wikimedia Commons — imágenes históricas reales (API pública, sin clave)
  2. Pollinations.ai   — imágenes generadas por IA (fallback o complemento)
  3. Imagen negra      — fallback total si todo falla

Salida: formato vertical 1080 × 1920 px (JPEG, quality=90).
"""
import os
import time
import requests
from urllib.parse import quote
from PIL import Image
from io import BytesIO


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades de imagen
# ─────────────────────────────────────────────────────────────────────────────

def redimensionar_a_vertical(
    img: Image.Image,
    target_w: int = 1080,
    target_h: int = 1920,
) -> Image.Image:
    """
    Redimensiona img a target_w × target_h manteniendo aspect ratio.
    Las zonas vacías se rellenan con negro (letterbox/pillarbox).
    """
    img = img.convert("RGB")
    orig_w, orig_h = img.size
    ratio_orig   = orig_w / orig_h
    ratio_target = target_w / target_h

    if ratio_orig > ratio_target:
        # Imagen más ancha que el objetivo → ajustar por alto
        new_h = target_h
        new_w = int(orig_w * (target_h / orig_h))
    else:
        # Imagen más alta (o misma ratio) → ajustar por ancho
        new_w = target_w
        new_h = int(orig_h * (target_w / orig_w))

    img_resized = img.resize((new_w, new_h), Image.LANCZOS)
    fondo = Image.new("RGB", (target_w, target_h), (0, 0, 0))
    offset_x = (target_w - new_w) // 2
    offset_y = (target_h - new_h) // 2
    fondo.paste(img_resized, (offset_x, offset_y))
    return fondo


# ─────────────────────────────────────────────────────────────────────────────
# Fuente 1 — Wikimedia Commons
# ─────────────────────────────────────────────────────────────────────────────

WC_API   = "https://commons.wikimedia.org/w/api.php"
WC_HDRS  = {
    "User-Agent": (
        "YoutubeContentBot/1.0 "
        "(https://github.com/ramirobarrasoto/youtube-pipeline; "
        "contact rbarrasoto@gmail.com) Python/requests"
    )
}
WC_MIN_W = 700   # ancho mínimo para aceptar la imagen
WC_MIN_H = 500   # alto mínimo


def _terminos_busqueda(tema: str) -> list[str]:
    """
    Genera variantes de búsqueda a partir del tema (puede estar en español).
    Prueba el tema completo y también las primeras palabras significativas.
    """
    terminos = [tema]
    palabras = tema.split()
    if len(palabras) > 3:
        terminos.append(" ".join(palabras[:4]))
    if len(palabras) > 1:
        terminos.append(" ".join(palabras[:2]))
    # Si hay números (años, ediciones…) agregarlos solos como keyword
    nums = [w for w in palabras if w.isdigit() and len(w) >= 4]
    if nums:
        terminos.append(nums[0])
    return list(dict.fromkeys(terminos))  # deduplica conservando orden


def buscar_imagenes_wikimedia(tema: str, cantidad: int = 8) -> list[dict]:
    """
    Busca imágenes en Wikimedia Commons para el tema indicado.

    Returns:
        Lista de dicts: {"url", "width", "height", "title"}, ordenada
        de mayor a menor resolución. Puede estar vacía.
    """
    imagenes: list[dict] = []
    vistos: set[str]    = set()

    for termino in _terminos_busqueda(tema):
        if len(imagenes) >= cantidad * 2:
            break

        params = {
            "action":        "query",
            "generator":     "search",
            "gsrsearch":     termino,
            "gsrnamespace":  6,      # File namespace
            "gsrlimit":      20,
            "prop":          "imageinfo",
            "iiprop":        "url|size",
            "format":        "json",
            "formatversion": 2,
        }

        try:
            resp = requests.get(WC_API, params=params, headers=WC_HDRS, timeout=20)
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", [])

            for page in pages:
                for info in page.get("imageinfo", []):
                    url   = info.get("url", "")
                    width = info.get("width", 0)
                    height= info.get("height", 0)

                    if url in vistos:
                        continue
                    vistos.add(url)

                    # Solo JPEG / PNG / WebP y resolución suficiente
                    base_url = url.lower().split("?")[0]
                    if not any(base_url.endswith(e) for e in (".jpg", ".jpeg", ".png", ".webp")):
                        continue
                    if width < WC_MIN_W or height < WC_MIN_H:
                        continue

                    imagenes.append({
                        "url":    url,
                        "width":  width,
                        "height": height,
                        "title":  page.get("title", ""),
                    })

        except Exception as exc:
            print(f"  ⚠️  Error en búsqueda Wikimedia ('{termino}'): {exc}")
            time.sleep(1)

    # Ordenar por resolución (mayor primero) y limitar
    imagenes.sort(key=lambda x: x["width"] * x["height"], reverse=True)
    return imagenes[:cantidad * 2]   # devolver el doble por si alguna falla al descargar


def descargar_imagen_wikimedia(url: str, output_path: str) -> bool:
    """Descarga una imagen de Wikimedia, la redimensiona y guarda como JPEG."""
    try:
        resp = requests.get(url, headers=WC_HDRS, timeout=30)
        if resp.status_code == 200 and len(resp.content) > 5_000:
            img = Image.open(BytesIO(resp.content))
            img = redimensionar_a_vertical(img)
            img.save(output_path, "JPEG", quality=90)
            return True
        print(f"  ⚠️  Wikimedia HTTP {resp.status_code} o contenido vacío")
    except Exception as exc:
        print(f"  ⚠️  Error descargando {url[:60]}…: {exc}")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Fuente 2 — Pollinations.ai (fallback / complemento)
# ─────────────────────────────────────────────────────────────────────────────

def generar_imagen_pollinations(
    prompt: str,
    output_path: str,
    intentos: int = 3,
) -> bool:
    """Genera una imagen 1080×1920 con Pollinations.ai."""
    url = (
        f"https://image.pollinations.ai/prompt/{quote(prompt)}"
        f"?width=1080&height=1920&nologo=true&seed={int(time.time())}"
    )
    for intento in range(intentos):
        try:
            response = requests.get(url, timeout=90)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content)).convert("RGB")
                img.save(output_path, "JPEG", quality=90)
                return True
            print(f"  ⚠️  Pollinations intento {intento+1}: HTTP {response.status_code}")
            time.sleep(5)
        except Exception as exc:
            print(f"  ⚠️  Pollinations intento {intento+1}: {exc}")
            time.sleep(5)
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Función principal
# ─────────────────────────────────────────────────────────────────────────────

def generar_imagenes(
    tema: str,
    output_dir: str = "videos_output/images",
    cantidad: int = 4,
    estilo: str = "cinematic, dramatic, historical",
) -> list[str]:
    """
    Obtiene `cantidad` imágenes para el tema indicado.

    Prioridad:
      1. Wikimedia Commons (imágenes históricas reales)
      2. Pollinations.ai  (IA generativa, complemento o fallback)
      3. Imagen negra     (fallback absoluto)

    Returns:
        Lista de rutas a los archivos JPEG generados.
    """
    os.makedirs(output_dir, exist_ok=True)
    imagenes: list[str] = []

    # ── 1. Wikimedia Commons ──────────────────────────────────────────────
    print(f"\n  🌐  Buscando imágenes históricas en Wikimedia Commons: '{tema}'...")
    resultados_wiki = buscar_imagenes_wikimedia(tema, cantidad=cantidad)

    if resultados_wiki:
        print(f"  📋  {len(resultados_wiki)} imagen(es) encontrada(s) en Wikimedia Commons")
        for resultado in resultados_wiki:
            if len(imagenes) >= cantidad:
                break
            idx         = len(imagenes) + 1
            output_path = os.path.join(output_dir, f"img{idx}.jpg")
            titulo_corto = resultado["title"][:55]
            print(
                f"  ⬇️   Descargando {idx}/{cantidad}: {titulo_corto}… "
                f"({resultado['width']}×{resultado['height']})"
            )
            if descargar_imagen_wikimedia(resultado["url"], output_path):
                imagenes.append(output_path)
                print(f"  ✅  Imagen {idx} guardada (Wikimedia)")
            else:
                print("  ⚠️  Falló, probando siguiente resultado...")
    else:
        print("  ℹ️   No se encontraron imágenes en Wikimedia Commons para este tema")

    # ── 2. Pollinations.ai (complemento / fallback) ───────────────────────
    faltantes = cantidad - len(imagenes)
    if faltantes > 0:
        fuente_label = "complemento" if imagenes else "fuente principal (fallback)"
        print(
            f"\n  🎨  Generando {faltantes} imagen(es) con IA Pollinations.ai "
            f"({fuente_label})..."
        )
        prompts = [
            f"{tema}, {estilo}, epic moment",
            f"{tema}, {estilo}, wide angle shot",
            f"{tema}, {estilo}, close up dramatic",
            f"{tema}, {estilo}, emotional atmosphere",
            f"{tema}, {estilo}, action scene",
            f"{tema}, {estilo}, historical context",
            f"{tema}, {estilo}, crowd reaction",
            f"{tema}, {estilo}, iconic moment",
        ]
        for j, prompt in enumerate(prompts[:faltantes]):
            idx         = len(imagenes) + 1
            output_path = os.path.join(output_dir, f"img{idx}.jpg")
            print(f"  🖼️   Generando imagen IA {j+1}/{faltantes}...")
            if generar_imagen_pollinations(prompt, output_path):
                imagenes.append(output_path)
                print(f"  ✅  Imagen IA {j+1} generada")
            else:
                print(f"  ⚠️  Imagen IA {j+1} falló, continuando...")

    # ── 3. Fallback absoluto ──────────────────────────────────────────────
    if not imagenes:
        print("  ⚠️  Usando imagen de fallback (fondo negro)...")
        img          = Image.new("RGB", (1080, 1920), color=(20, 20, 20))
        fallback_path = os.path.join(output_dir, "img1.jpg")
        img.save(fallback_path)
        imagenes.append(fallback_path)

    print(f"\n  ✅  {len(imagenes)} imagen(es) lista(s) "
          f"({sum(1 for p in imagenes if 'img' in os.path.basename(p) and not 'custom' in p)} reales / IA)")
    return imagenes


# ─────────────────────────────────────────────────────────────────────────────
# CLI rápido para testing
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    generar_imagenes("1930 FIFA World Cup Final Uruguay", output_dir="/tmp/test_images", cantidad=4)
