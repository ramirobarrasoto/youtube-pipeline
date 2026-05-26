import os
import numpy as np
from pathlib import Path
from PIL import Image
from moviepy.editor import (
    ImageClip, AudioFileClip, concatenate_videoclips,
    CompositeVideoClip
)

def aplicar_ken_burns(img_array, duracion, fps=24, efecto=None):
    """Aplica efecto Ken Burns (zoom + paneo) a una imagen."""
    h, w = img_array.shape[:2]
    frames = int(duracion * fps)
    
    efectos = [
        {"zoom_start": 1.0, "zoom_end": 1.15, "x": 0, "y": 0},      # Zoom in centro
        {"zoom_start": 1.15, "zoom_end": 1.0, "x": 0, "y": 0},      # Zoom out centro
        {"zoom_start": 1.0, "zoom_end": 1.12, "x": -0.05, "y": 0},  # Zoom + paneo derecha
        {"zoom_start": 1.0, "zoom_end": 1.12, "x": 0.05, "y": 0},   # Zoom + paneo izquierda
        {"zoom_start": 1.0, "zoom_end": 1.1,  "x": 0, "y": -0.04},  # Zoom + paneo arriba
    ]
    
    if efecto is None:
        efecto = efectos[np.random.randint(len(efectos))]
    
    result_frames = []
    for i in range(frames):
        t = i / max(frames - 1, 1)
        zoom = efecto["zoom_start"] + (efecto["zoom_end"] - efecto["zoom_start"]) * t
        
        new_w = int(w / zoom)
        new_h = int(h / zoom)
        
        cx = w // 2 + int(efecto["x"] * w * t)
        cy = h // 2 + int(efecto["y"] * h * t)
        
        x1 = max(0, cx - new_w // 2)
        y1 = max(0, cy - new_h // 2)
        x2 = min(w, x1 + new_w)
        y2 = min(h, y1 + new_h)
        
        cropped = img_array[y1:y2, x1:x2]
        img_pil = Image.fromarray(cropped).resize((w, h), Image.LANCZOS)
        result_frames.append(np.array(img_pil))
    
    return result_frames

def crear_clip_con_kenburns(img_path, duracion, fps=24):
    """Crea un clip con efecto Ken Burns."""
    img = Image.open(str(img_path)).convert("RGB")
    img = img.resize((1080, 1920), Image.LANCZOS)
    img_array = np.array(img)
    
    frames = aplicar_ken_burns(img_array, duracion, fps)
    
    def make_frame(t):
        idx = min(int(t * fps), len(frames) - 1)
        return frames[idx]
    
    clip = ImageClip(img_array).set_duration(duracion)
    clip = clip.fl(lambda gf, t: frames[min(int(t * fps), len(frames) - 1)])
    
    return clip

def generar_video(
    audio_path,
    images_dir,
    output_path,
    fps=24,
    transicion_duracion=0.5
):
    print("⏳ Cargando audio...")
    audio = AudioFileClip(audio_path)
    duracion_total = audio.duration
    print(f"✅ Duración: {duracion_total:.1f} segundos")

    print("⏳ Cargando imágenes...")
    extensiones = [".jpg", ".jpeg", ".png", ".webp"]
    imagenes = []
    for ext in extensiones:
        imagenes += sorted(Path(images_dir).glob(f"*{ext}"))

    if not imagenes:
        print("❌ No se encontraron imágenes")
        return None

    print(f"✅ {len(imagenes)} imágenes encontradas")

    duracion_por_imagen = duracion_total / len(imagenes)
    print(f"⏳ Duración por imagen: {duracion_por_imagen:.1f} segundos")

    print("⏳ Aplicando efecto Ken Burns...")
    clips = []
    for i, img_path in enumerate(imagenes):
        print(f"  Procesando imagen {i+1}/{len(imagenes)}...")
        try:
            clip = crear_clip_con_kenburns(img_path, duracion_por_imagen, fps)
            clips.append(clip)
        except Exception as e:
            print(f"  ⚠️ Error en imagen {i+1}: {e}")
            img = Image.open(str(img_path)).convert("RGB")
            img = img.resize((1080, 1920), Image.LANCZOS)
            clip = ImageClip(np.array(img)).set_duration(duracion_por_imagen)
            clips.append(clip)

    print("⏳ Concatenando clips...")
    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio)

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    print("⏳ Exportando video... (puede tardar 2-5 minutos)")
    video.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        verbose=False,
        logger=None
    )

    print(f"✅ Video guardado en: {output_path}")
    return output_path

if __name__ == "__main__":
    generar_video(
        audio_path="videos_output/audio/narration.mp3",
        images_dir="videos_output/images",
        output_path="videos_output/final/video_ken_burns.mp4"
    )
