"""
Descarga pistas de música libre de derechos para los videos.

Fuentes en orden de preferencia:
  1. FreePD.com  — dominio público, descarga directa
  2. SoundHelix  — CC0, descarga directa (fallback genérico)

Uso:
    from descargar_musica import obtener_musica
    path = obtener_musica("epico")   # devuelve ruta al .mp3 o None
"""
import os
import time
import requests

MUSIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "music"
)

# Catálogo: género → filename + lista de URLs de descarga directa (en orden de prioridad)
MUSIC_CATALOG = {
    "epico": {
        "filename": "epico.mp3",
        "nombre":   "Épico / Orquestal",
        "urls": [
            "https://freepd.com/music/Heroic%20Age.mp3",
            "https://freepd.com/music/Black%20Vortex.mp3",
            "https://freepd.com/music/Arcadia.mp3",
            "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        ],
    },
    "dramatico": {
        "filename": "dramatico.mp3",
        "nombre":   "Dramático",
        "urls": [
            "https://freepd.com/music/Virtutes%20Instrumenti.mp3",
            "https://freepd.com/music/Space%20Fighter%20Loop.mp3",
            "https://freepd.com/music/Dark%20Fog.mp3",
            "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3",
        ],
    },
    "aventura": {
        "filename": "aventura.mp3",
        "nombre":   "Aventura",
        "urls": [
            "https://freepd.com/music/Majestic%20Hills.mp3",
            "https://freepd.com/music/Bassa%20Island%20Game%20Loop.mp3",
            "https://freepd.com/music/Sneaky%20Snitch.mp3",
            "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3",
        ],
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

MIN_SIZE_BYTES = 50_000   # descartar archivos menores a 50 KB
MAX_SIZE_BYTES = 30 * 1024 * 1024  # límite de 30 MB


def obtener_musica(genero: str) -> str | None:
    """
    Devuelve la ruta local al archivo mp3 para el género indicado.
    Lo descarga si no existe o está incompleto.

    Args:
        genero: "epico" | "dramatico" | "aventura"

    Returns:
        Ruta al archivo mp3, o None si no fue posible obtenerlo.
    """
    if genero not in MUSIC_CATALOG:
        print(f"  ⚠️  Género de música desconocido: '{genero}'")
        return None

    catalog    = MUSIC_CATALOG[genero]
    local_path = os.path.join(MUSIC_DIR, catalog["filename"])

    # Si ya existe y es válido, reutilizarlo
    if os.path.exists(local_path) and os.path.getsize(local_path) >= MIN_SIZE_BYTES:
        print(f"  🎵  Música en caché: {catalog['nombre']}")
        return local_path

    os.makedirs(MUSIC_DIR, exist_ok=True)
    print(f"  📥  Descargando música '{catalog['nombre']}'...")

    for i, url in enumerate(catalog["urls"], start=1):
        try:
            print(f"     Fuente {i}/{len(catalog['urls'])}: {url[:70]}...")
            resp = requests.get(url, headers=HEADERS, timeout=45, stream=True)

            if resp.status_code != 200:
                print(f"     ⚠️  HTTP {resp.status_code}")
                time.sleep(2)
                continue

            # Leer contenido con límite de tamaño
            chunks = []
            total  = 0
            for chunk in resp.iter_content(chunk_size=16_384):
                chunks.append(chunk)
                total += len(chunk)
                if total >= MAX_SIZE_BYTES:
                    break

            content = b"".join(chunks)

            if len(content) < MIN_SIZE_BYTES:
                print(f"     ⚠️  Archivo demasiado pequeño ({len(content)} bytes)")
                time.sleep(2)
                continue

            with open(local_path, "wb") as f:
                f.write(content)

            print(
                f"  ✅  Música descargada: {catalog['nombre']} "
                f"({len(content) // 1024} KB)"
            )
            return local_path

        except Exception as exc:
            print(f"     ⚠️  Error: {exc}")
            time.sleep(3)

    print(f"  ❌  No se pudo descargar música para el género '{genero}'")
    return None


if __name__ == "__main__":
    for g in MUSIC_CATALOG:
        p = obtener_musica(g)
        print(f"{g}: {p}")
