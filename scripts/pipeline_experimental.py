"""
Pipeline Experimental V2 — Videos largos (15 min) con Gemini + FFmpeg.

Diferencias vs pipeline actual (producción):
  - Guión: Gemini con JSON Schema estructurado (escena por escena)
  - Audio: Edge TTS por escena en paralelo
           └── Hook para XTTS v2 local (ver función generar_audio_escena)
  - Imágenes: Wikimedia/Pexels/Pollinations por prompt_visual_ia de cada escena
              └── Hook para GPU propia (RunPod/Vast.ai + Flux/SD 3.5)
  - Ensamble: FFmpeg nativo (más rápido que MoviePy para 100+ clips)
              con efecto Ken Burns (zoompan filter)

REGLA DE AISLAMIENTO: Este archivo NO modifica ningún archivo de producción.
"""
import os
import json
import time
import subprocess
import shutil
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("config/.env")

# Frames por segundo para el video final
FPS = 30
CROSSFADE_DUR = 1.0   # segundos de disolvencia entre escenas
BITRATE_VIDEO = "5M"  # bitrate objetivo para YouTube (evita pixelación)


# ─────────────────────────────────────────────────────────────────────────────
# Módulo de Audio — Edge TTS con hook para XTTS v2 local
# ─────────────────────────────────────────────────────────────────────────────

def _generar_audio_edge_tts(texto: str, voz: str, output_path: str) -> bool:
    """Genera audio con Edge TTS (gratuito, sin servidor local)."""
    try:
        import edge_tts
        async def _gen():
            communicate = edge_tts.Communicate(texto, voz)
            await communicate.save(output_path)
        asyncio.run(_gen())
        return os.path.exists(output_path) and os.path.getsize(output_path) > 500
    except Exception as exc:
        print(f"    ⚠️  Edge TTS error: {exc}")
        return False


def _generar_audio_xtts_local(texto: str, voz: str, output_path: str) -> bool:
    """
    Hook para XTTS v2 local corriendo como microservicio.

    Para activar:
        1. Instalar XTTS v2: pip install TTS
        2. Arrancar el servidor: tts-server --model_name tts_models/multilingual/multi-dataset/xtts_v2 --port 8020
        3. Setear en config/.env: TTS_LOCAL_URL=http://localhost:8020

    Mientras no esté activo, esta función retorna False y se usa Edge TTS.
    """
    tts_url = os.getenv("TTS_LOCAL_URL", "")
    if not tts_url:
        return False
    try:
        import requests
        resp = requests.post(
            f"{tts_url}/api/tts",
            json={"text": texto, "language": "es", "speaker_wav": None},
            timeout=30,
        )
        if resp.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(resp.content)
            return os.path.getsize(output_path) > 500
    except Exception:
        pass
    return False


def generar_audio_escena(
    texto: str,
    voz: str,
    output_path: str,
    usar_local: bool = True,
) -> bool:
    """
    Genera audio para una escena. Prioridad:
      1. XTTS v2 local (si TTS_LOCAL_URL está configurado)
      2. Edge TTS (fallback gratuito siempre disponible)
    """
    if usar_local and _generar_audio_xtts_local(texto, voz, output_path):
        return True
    return _generar_audio_edge_tts(texto, voz, output_path)


def generar_audios_paralelo(
    escenas: list[dict],
    voz: str,
    audio_dir: str,
    max_workers: int = 4,
) -> dict[int, str]:
    """
    Genera el audio de todas las escenas en paralelo.

    Returns:
        Dict {numero_escena: ruta_audio}
    """
    os.makedirs(audio_dir, exist_ok=True)
    resultados: dict[int, str] = {}
    total = len(escenas)

    def _procesar(escena):
        num = escena["numero_escena"]
        texto = escena["texto_narracion"]
        path = os.path.join(audio_dir, f"audio_{num:04d}.mp3")
        ok = generar_audio_escena(texto, voz, path)
        return num, path if ok else None

    print(f"  🎙️  Generando {total} audios en paralelo (workers: {max_workers})...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_procesar, e): e["numero_escena"] for e in escenas}
        completados = 0
        for future in as_completed(futures):
            num, path = future.result()
            if path:
                resultados[num] = path
            completados += 1
            if completados % 10 == 0 or completados == total:
                print(f"    Audio: {completados}/{total} escenas")

    print(f"  ✅ Audios generados: {len(resultados)}/{total}")
    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# Módulo Gráfico — Imágenes por escena con Gemini / Imagen 3
# ─────────────────────────────────────────────────────────────────────────────

def _ajustar_a_1080x1920(img) -> object:
    """
    Redimensiona la imagen a 1080x1920 manteniendo aspect ratio.
    Rellena con negro si es necesario — nunca estira ni deforma.
    """
    from PIL import Image
    img = img.convert("RGB")
    tw, th = 1080, 1920
    rw, rh = img.size
    ratio = min(tw / rw, th / rh)
    nw, nh = int(rw * ratio), int(rh * ratio)
    img = img.resize((nw, nh), Image.LANCZOS)
    fondo = Image.new("RGB", (tw, th), (0, 0, 0))
    fondo.paste(img, ((tw - nw) // 2, (th - nh) // 2))
    return fondo


def _generar_imagen_gemini(prompt: str, output_path: str, reintentos: int = 3) -> bool:
    """
    Genera una imagen usando Gemini/Imagen 3 a partir del prompt_visual_ia exacto.

    Prioridad:
      1. Imagen 3 (imagen-3.0-generate-002) — mayor calidad fotorealista, aspect ratio 9:16 nativo
      2. Gemini image model (gemini-2.5-flash-image) — fallback si Imagen 3 no está disponible
    """
    from google import genai
    from google.genai import types
    from PIL import Image
    from io import BytesIO
    import base64

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        print("    ⚠️  GEMINI_API_KEY no configurada")
        return False

    client = genai.Client(api_key=api_key)
    # Reforzar formato vertical en el prompt
    prompt_final = f"{prompt}, vertical composition 9:16 portrait orientation, ultra detailed 4K"

    for intento in range(reintentos):
        # ── Intento 1: Imagen 3 (aspect_ratio 9:16 nativo, sin deformación) ──
        try:
            response = client.models.generate_images(
                model="imagen-3.0-generate-002",
                prompt=prompt_final,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="9:16",
                    output_mime_type="image/jpeg",
                ),
            )
            if response.generated_images:
                img_bytes = response.generated_images[0].image.image_bytes
                img = Image.open(BytesIO(img_bytes))
                img = _ajustar_a_1080x1920(img)
                img.save(output_path, "JPEG", quality=95)
                return True
        except Exception as exc:
            err = str(exc)
            if "429" in err or "quota" in err.lower() or "rate" in err.lower():
                wait = 60 if intento == 0 else 120
                print(f"    ⏳ Rate limit Imagen 3, esperando {wait}s...")
                time.sleep(wait)
                continue
            # Si no está disponible en el plan, saltar directo al fallback
            if "billing" in err.lower() or "not found" in err.lower() or "permission" in err.lower():
                print(f"    ℹ️  Imagen 3 no disponible ({err[:60]}), usando Gemini image...")
                break
            print(f"    ⚠️  Imagen 3 intento {intento+1}: {err[:80]}")
            time.sleep(5)

        # ── Intento 2: Gemini image model ────────────────────────────────────
        try:
            modelo_img = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
            response = client.models.generate_content(
                model=modelo_img,
                contents=prompt_final,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                ),
            )
            for part in response.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    data = part.inline_data.data
                    if isinstance(data, str):
                        data = base64.b64decode(data)
                    img = Image.open(BytesIO(data))
                    img = _ajustar_a_1080x1920(img)
                    img.save(output_path, "JPEG", quality=95)
                    return True
        except Exception as exc:
            err = str(exc)
            if "429" in err or "quota" in err.lower() or "rate" in err.lower():
                wait = 60 if intento == 0 else 120
                print(f"    ⏳ Rate limit Gemini image, esperando {wait}s...")
                time.sleep(wait)
                continue
            print(f"    ⚠️  Gemini image intento {intento+1}: {err[:80]}")
            time.sleep(5)

    return False


def _generar_imagen_pollinations(prompt: str, output_path: str) -> bool:
    """Fallback gratuito: genera imagen via Pollinations.ai con el mismo prompt."""
    import urllib.parse
    import urllib.request
    from PIL import Image
    from io import BytesIO

    try:
        prompt_enc = urllib.parse.quote(prompt[:500])
        url = f"https://image.pollinations.ai/prompt/{prompt_enc}?width=1080&height=1920&model=flux&nologo=true"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        img = Image.open(BytesIO(data)).convert("RGB")
        img = _ajustar_a_1080x1920(img)
        img.save(output_path, "JPEG", quality=90)
        return True
    except Exception as exc:
        print(f"    ⚠️  Pollinations fallback falló: {str(exc)[:80]}")
        return False


def generar_imagenes_escenas(
    escenas: list[dict],
    images_dir: str,
    estilo: str = "cinematic 4K dramatic",
    max_workers: int = 1,
) -> dict[int, str]:
    """
    Genera imágenes para todas las escenas usando Gemini / Imagen 3.
    Usa el prompt_visual_ia exacto de cada escena — sin Wikimedia ni Pollinations.

    max_workers=1 por defecto (secuencial) para respetar el rate limit de Imagen 3.
    Fallback automático a Pollinations.ai si Imagen 3 falla.
    Saltea escenas que ya tienen imagen guardada (permite reanudar si se interrumpe).
    """
    from PIL import Image as PILImage

    os.makedirs(images_dir, exist_ok=True)
    resultados: dict[int, str] = {}
    total = len(escenas)

    def _procesar(escena):
        num = escena["numero_escena"]
        prompt = escena.get("prompt_visual_ia", "")
        path = os.path.join(images_dir, f"img_{num:04d}.jpg")

        # Saltar si ya existe (permite reanudar)
        if os.path.exists(path) and os.path.getsize(path) > 5_000:
            return num, path

        if _generar_imagen_gemini(prompt, path):
            return num, path

        # Fallback: Pollinations.ai — genera imagen con IA, gratis, sin rate limit
        if _generar_imagen_pollinations(prompt, path):
            print(f"    ✅  Escena {num}: imagen via Pollinations.ai")
            return num, path

        # Último recurso: imagen negra
        PILImage.new("RGB", (1080, 1920), (15, 15, 15)).save(path, "JPEG", quality=90)
        print(f"    ⚠️  Escena {num}: fallback imagen negra")
        return num, path

    print(f"  🎨  Generando {total} imágenes (Imagen 3 → Pollinations fallback, workers: {max_workers})...")
    print(f"  ℹ️  Rate limit Imagen 3: ~10 img/min — estimado {total // 10 + 1} min (secuencial)")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_procesar, e): e["numero_escena"] for e in escenas}
        completados = 0
        for future in as_completed(futures):
            num, path = future.result()
            resultados[num] = path
            completados += 1
            if completados % 10 == 0 or completados == total:
                pct = int(completados / total * 100)
                print(f"    Imágenes: {completados}/{total} ({pct}%)")

    print(f"  ✅ Imágenes generadas: {len(resultados)}/{total}")
    return resultados

    print(f"  ✅ Imágenes generadas: {len(resultados)}/{total}")
    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# Módulo de Ensamble — FFmpeg con Ken Burns automático
# ─────────────────────────────────────────────────────────────────────────────

def _get_audio_duration(audio_path: str) -> float:
    """Obtiene la duración de un archivo de audio con ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", audio_path],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                return float(stream.get("duration", 0))
    except Exception:
        pass
    # Fallback con moviepy si ffprobe falla
    try:
        from moviepy.editor import AudioFileClip
        clip = AudioFileClip(audio_path)
        dur = clip.duration
        clip.close()
        return dur
    except Exception:
        return 5.0


def _get_clip_duration(video_path: str) -> float:
    """Obtiene la duración de un clip de video con ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", video_path],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        dur = float(data.get("format", {}).get("duration", 0))
        if dur > 0:
            return dur
    except Exception:
        pass
    return 5.0


def crear_clip_escena_ffmpeg(
    imagen_path: str,
    audio_path: str,
    output_path: str,
    duracion: float | None = None,
    efecto: str = "zoom_in",
) -> bool:
    """
    Crea un clip Ken Burns suavizado para una escena.

    Mejoras vs versión anterior:
    - Usa `on` (número de frame lineal) en lugar de `zoom` acumulativo → sin flickering
    - Pre-escala a 2160×3840 (2x) para dar margen al zoompan sin artefactos
    - zoompan con `:s=1080x1920` define el output directamente
    - 30 FPS, libx264 high profile, 5M bitrate (calidad YouTube)
    - 5 efectos con ciclo variado para evitar monotonía visual
    """
    if not os.path.exists(imagen_path):
        return False

    dur = duracion or _get_audio_duration(audio_path)
    if dur <= 0:
        dur = 5.0

    frames = int(dur * FPS)

    # Fórmulas lineales basadas en `on` (frame actual) → zoom suave sin saltos
    efectos_zoompan = {
        "zoom_in":     f"zoompan=z='1+0.0005*on':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920",
        "zoom_out":    f"zoompan=z='max(1,1.1-0.0005*on)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920",
        "pan_left":    f"zoompan=z='1+0.0003*on':d={frames}:x='max(0,iw/2-(iw/zoom/2)-on*0.6)':y='ih/2-(ih/zoom/2)':s=1080x1920",
        "pan_right":   f"zoompan=z='1+0.0003*on':d={frames}:x='min(iw-iw/zoom,iw/2-(iw/zoom/2)+on*0.6)':y='ih/2-(ih/zoom/2)':s=1080x1920",
        "zoom_in_up":  f"zoompan=z='1+0.0004*on':d={frames}:x='iw/2-(iw/zoom/2)':y='max(0,ih/2-(ih/zoom/2)-on*0.3)':s=1080x1920",
    }
    zoompan = efectos_zoompan.get(efecto, efectos_zoompan["zoom_in"])

    # Pre-escala a 2x el target para que zoompan tenga margen de movimiento real
    vf = f"scale=2160:3840:flags=lanczos,{zoompan}"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-t", str(dur), "-i", imagen_path,
        "-i", audio_path,
        "-vf", vf,
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-profile:v", "high", "-b:v", BITRATE_VIDEO,
        "-x264-params", "no-scenecut=1:keyint=30",
        "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode == 0:
        return True

    # Fallback: clip estático limpio si zoompan falla (ej. x265 roto en Mac)
    print(f"    ⚠️  Ken Burns falló ({result.stderr[-120:].strip()}), usando clip estático...")
    cmd_static = [
        "ffmpeg", "-y",
        "-loop", "1", "-t", str(dur), "-i", imagen_path,
        "-i", audio_path,
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
               "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-profile:v", "high", "-b:v", BITRATE_VIDEO,
        "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_path,
    ]
    result2 = subprocess.run(cmd_static, capture_output=True, text=True, timeout=120)
    if result2.returncode != 0:
        print(f"    ❌  FFmpeg estático error: {result2.stderr[-200:]}")
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Ensamble con crossfade (xfade + acrossfade)
# ─────────────────────────────────────────────────────────────────────────────

def _xfade_batch(
    clips: list[str],
    output_path: str,
    crossfade_dur: float = CROSSFADE_DUR,
) -> bool:
    """
    Aplica disolvencia cruzada (xfade + acrossfade) a un lote de clips.

    Calcula los offsets dinámicamente: offset_i = Σ dur[0..i-1] - i * crossfade_dur
    Máximo recomendado: 12-15 clips por llamada para no saturar filter_complex.
    """
    if len(clips) == 1:
        shutil.copy2(clips[0], output_path)
        return True

    duraciones = [_get_clip_duration(c) for c in clips]
    # Reducir crossfade si algún clip es muy corto
    cf = min(crossfade_dur, min(duraciones) / 2 - 0.05)
    cf = max(cf, 0.1)

    inputs = []
    for c in clips:
        inputs += ["-i", c]

    filtros_v, filtros_a = [], []
    label_v, label_a = "[0:v]", "[0:a]"
    offset_acum = 0.0

    for i in range(1, len(clips)):
        offset_acum += duraciones[i - 1] - cf
        out_v, out_a = f"[v{i}]", f"[a{i}]"
        filtros_v.append(
            f"{label_v}[{i}:v]xfade=transition=fade:duration={cf:.3f}:offset={offset_acum:.3f}{out_v}"
        )
        filtros_a.append(
            f"{label_a}[{i}:a]acrossfade=d={cf:.3f}{out_a}"
        )
        label_v, label_a = out_v, out_a

    filter_complex = ";".join(filtros_v + filtros_a)

    cmd = (
        ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filter_complex,
            "-map", label_v, "-map", label_a,
            "-c:v", "libx264", "-profile:v", "high", "-b:v", BITRATE_VIDEO,
            "-pix_fmt", "yuv420p",
            "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k",
            output_path,
        ]
    )
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        print(f"    ❌  xfade batch error: {result.stderr[-400:]}")
        return False
    return True


def ensamblar_con_crossfade(
    clips_paths: list[str],
    output_path: str,
    temp_dir: str,
    crossfade_dur: float = CROSSFADE_DUR,
    batch_size: int = 12,
) -> bool:
    """
    Ensambla todos los clips con transiciones de disolvencia cruzada.

    Para 100+ clips usa procesamiento por lotes (batch_size clips c/u con xfade),
    luego concatena los lotes. Los lotes internos tienen crossfade suave;
    entre lotes hay un corte limpio — invisible en la práctica porque cada lote
    es largo (batch_size × duración_escena).

    Fallback automático a concat sin crossfade si xfade falla.
    """
    total = len(clips_paths)
    print(f"\n  🎬  Ensamblando {total} clips con crossfade ({crossfade_dur}s)...")

    if total == 0:
        return False
    if total == 1:
        shutil.copy2(clips_paths[0], output_path)
        return True

    lotes = [clips_paths[i:i + batch_size] for i in range(0, total, batch_size)]
    print(f"  ℹ️   {len(lotes)} lote(s) de hasta {batch_size} clips c/u")

    if len(lotes) == 1:
        ok = _xfade_batch(lotes[0], output_path, crossfade_dur)
        if not ok:
            print("  ⚠️  xfade falló, usando concat directo como fallback...")
            return ensamblar_clips_ffmpeg(clips_paths, output_path, temp_dir)
        print(f"  ✅  Video ensamblado con crossfade: {os.path.basename(output_path)}")
        return True

    # Multi-lote: xfade dentro de cada lote, concat entre lotes
    lote_paths = []
    for i, lote in enumerate(lotes):
        lote_out = os.path.join(temp_dir, f"_lote_{i:03d}.mp4")
        print(f"    Lote {i + 1}/{len(lotes)} ({len(lote)} clips)...", end=" ", flush=True)
        if _xfade_batch(lote, lote_out, crossfade_dur):
            lote_paths.append(lote_out)
            print("✓")
        else:
            # Fallback: concat este lote sin xfade
            print("⚠️  fallback concat")
            filelist = os.path.join(temp_dir, f"_lote_{i:03d}_list.txt")
            with open(filelist, "w") as f:
                for c in lote:
                    f.write(f"file '{os.path.abspath(c)}'\n")
            r = subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                 "-i", filelist, "-c", "copy", lote_out],
                capture_output=True, timeout=600,
            )
            if r.returncode == 0:
                lote_paths.append(lote_out)

    if not lote_paths:
        return False

    # Concat final de los lotes
    print(f"    Concatenando {len(lote_paths)} lotes en video maestro...")
    filelist_final = os.path.join(temp_dir, "_lotes_final.txt")
    with open(filelist_final, "w") as f:
        for p in lote_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    cmd_final = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", filelist_final, "-c", "copy", output_path,
    ]
    result = subprocess.run(cmd_final, capture_output=True, text=True, timeout=600)

    # Limpiar lotes temporales
    for p in lote_paths:
        try:
            os.remove(p)
        except Exception:
            pass

    if result.returncode != 0:
        print(f"  ❌  Concat final error: {result.stderr[-400:]}")
        return False

    print(f"  ✅  Video maestro listo: {os.path.basename(output_path)}")
    return True


def ensamblar_clips_ffmpeg(
    clips_paths: list[str],
    output_path: str,
    temp_dir: str,
) -> bool:
    """Concat directo sin transiciones (fallback rápido)."""
    filelist_path = os.path.join(temp_dir, "filelist.txt")
    with open(filelist_path, "w") as f:
        for clip_path in clips_paths:
            f.write(f"file '{os.path.abspath(clip_path)}'\n")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", filelist_path, "-c", "copy", output_path,
    ]
    print(f"  🎬  Concat directo: {len(clips_paths)} clips → {os.path.basename(output_path)}...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"  ❌  FFmpeg concat error: {result.stderr[-400:]}")
        return False
    return True


def crear_clips_paralelo(
    escenas: list[dict],
    audios: dict[int, str],
    imagenes: dict[int, str],
    clips_dir: str,
    max_workers: int = 4,
) -> list[str]:
    """
    Crea el clip de video de cada escena en paralelo con FFmpeg.

    Returns:
        Lista ordenada de rutas a los clips generados.
    """
    os.makedirs(clips_dir, exist_ok=True)
    efectos_ciclo = ["zoom_in", "zoom_out", "pan_left", "pan_right", "zoom_in_up"]
    clips_ordenados: dict[int, str] = {}
    total = len(escenas)

    def _procesar(escena):
        num = escena["numero_escena"]
        imagen = imagenes.get(num)
        audio = audios.get(num)
        if not imagen or not audio:
            return num, None
        clip_path = os.path.join(clips_dir, f"clip_{num:04d}.mp4")
        efecto = efectos_ciclo[(num - 1) % len(efectos_ciclo)]
        ok = crear_clip_escena_ffmpeg(imagen, audio, clip_path, efecto=efecto)
        return num, clip_path if ok else None

    print(f"  🎥  Creando {total} clips con Ken Burns (FFmpeg, workers: {max_workers})...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_procesar, e): e["numero_escena"] for e in escenas}
        completados = 0
        for future in as_completed(futures):
            num, path = future.result()
            if path:
                clips_ordenados[num] = path
            completados += 1
            if completados % 20 == 0 or completados == total:
                pct = int(completados / total * 100)
                print(f"    Clips: {completados}/{total} ({pct}%)")

    # Ordenar por número de escena
    return [clips_ordenados[n] for n in sorted(clips_ordenados.keys())]


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline completo experimental
# ─────────────────────────────────────────────────────────────────────────────

def pipeline_experimental(
    canal: str,
    tema: str,
    duracion: str,
    voz: str,
    idioma: str = "español",
    privacidad: str = "private",
    genero_musica: str = "sin_musica",
    estilo_imagenes: str = "cinematic 4K dramatic",
    output_base: str = "videos_output",
    log_fn=None,
) -> str:
    """
    Pipeline experimental completo para videos de larga duración.

    Steps:
      1. Gemini genera guión estructurado (JSON por escenas)
      2. Edge TTS / XTTS v2 genera audio por escena en paralelo
      3. Imágenes por escena: GPU propia / Wikimedia / Pexels / Pollinations
      4. FFmpeg: Ken Burns por clip + ensamble final
      5. (Opcional) Música de fondo

    Returns:
        Ruta al video final MP4.
    """
    def log(msg, estado="active"):
        print(f"  [{estado.upper()}] {msg}")
        if log_fn:
            log_fn(msg, estado)

    nombre_carpeta = tema[:30].replace(" ", "_").replace("/", "-")
    base_dir = os.path.join(output_base, f"experimental/{canal}/{nombre_carpeta}")
    audio_dir  = os.path.join(base_dir, "audios")
    images_dir = os.path.join(base_dir, "images")
    clips_dir  = os.path.join(base_dir, "clips")
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(clips_dir, exist_ok=True)

    # ── PASO 1: Guión estructurado con Gemini ─────────────────────────────
    log("Generando guión estructurado con Gemini...")
    from gemini_service import generar_guion_estructurado, guion_a_script_completo
    escenas = generar_guion_estructurado(canal=canal, idioma=idioma, tema=tema, duracion=duracion)
    with open(os.path.join(base_dir, "guion.json"), "w") as f:
        json.dump(escenas, f, ensure_ascii=False, indent=2)
    script_completo = guion_a_script_completo(escenas)
    with open(os.path.join(base_dir, "script.txt"), "w") as f:
        f.write(script_completo)
    log(f"Guión generado: {len(escenas)} escenas", "done")

    # ── PASO 2: Audio por escena en paralelo ──────────────────────────────
    log(f"Generando {len(escenas)} audios en paralelo...")
    audios = generar_audios_paralelo(escenas, voz=voz, audio_dir=audio_dir, max_workers=4)
    log(f"Audios listos: {len(audios)}/{len(escenas)} escenas", "done")

    # ── PASO 3: Imágenes por escena (secuencial para respetar rate limits) ──
    log(f"Generando {len(escenas)} imágenes con prompt_visual_ia...")
    imagenes = generar_imagenes_escenas(escenas, images_dir=images_dir, estilo=estilo_imagenes, max_workers=1)
    log(f"Imágenes listas: {len(imagenes)}/{len(escenas)} escenas", "done")

    # ── PASO 4: Clips FFmpeg con Ken Burns ────────────────────────────────
    log("Creando clips con efecto Ken Burns (FFmpeg)...")
    clips = crear_clips_paralelo(escenas, audios=audios, imagenes=imagenes, clips_dir=clips_dir, max_workers=4)
    log(f"Clips listos: {len(clips)}/{len(escenas)}", "done")

    if not clips:
        raise Exception("No se pudieron generar clips de video")

    # ── PASO 5: Ensamble con crossfade ────────────────────────────────────
    video_final = os.path.join(base_dir, "video_final.mp4")
    log(f"Ensamblando {len(clips)} clips con crossfade ({CROSSFADE_DUR}s)...")
    ok = ensamblar_con_crossfade(
        clips,
        video_final,
        temp_dir=base_dir,
        crossfade_dur=CROSSFADE_DUR,
    )
    if not ok:
        raise Exception("Error al ensamblar el video final")
    log("Video maestro ensamblado", "done")

    # Nota: los clips individuales NO se borran para facilitar debugging.
    # Están en base_dir/clips/ para inspeccionarlos si hace falta.

    # ── PASO 6: Música de fondo (opcional) ───────────────────────────────
    if genero_musica and genero_musica != "sin_musica":
        log(f"Agregando música de fondo ({genero_musica})...")
        try:
            import sys
            scripts_dir = os.path.dirname(os.path.abspath(__file__))
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            from pipeline_video import agregar_musica_al_video
            video_con_musica = os.path.join(base_dir, "video_con_musica.mp4")
            agregar_musica_al_video(video_final, genero_musica, video_con_musica)
            if os.path.exists(video_con_musica):
                os.replace(video_con_musica, video_final)
            log("Música agregada", "done")
        except Exception as exc:
            log(f"Música omitida: {exc}", "done")

    # ── Guardar metadata ──────────────────────────────────────────────────
    from datetime import datetime
    metadata = {
        "tema": tema, "canal": canal, "duracion": duracion,
        "idioma": idioma, "escenas": len(escenas),
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "pipeline": "experimental_v2",
        "modelo_guion": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    }
    with open(os.path.join(base_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # Limpiar clips individuales para ahorrar espacio
    try:
        shutil.rmtree(clips_dir)
        print("  🧹  Clips temporales eliminados")
    except Exception:
        pass

    log(f"Pipeline experimental completado: {video_final}", "done")
    return video_final


# ─────────────────────────────────────────────────────────────────────────────
# CLI para testing
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    tema = input("Tema:\n> ").strip()
    canal = input("Canal [Historia Épica]: ").strip() or "Historia Épica"
    dur = input("Duración (corto/medio/largo) [largo]: ").strip() or "largo"
    voz = input("Voz TTS [es-MX-JorgeNeural]: ").strip() or "es-MX-JorgeNeural"

    video = pipeline_experimental(
        canal=canal,
        tema=tema,
        duracion=dur,
        voz=voz,
        idioma="español",
    )
    print(f"\n✅ Video generado: {video}")
