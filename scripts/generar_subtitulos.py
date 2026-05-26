import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from faster_whisper import WhisperModel
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip

def transcribir_audio(audio_path):
    print("⏳ Cargando modelo Whisper...")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    print("⏳ Transcribiendo audio...")
    segments, info = model.transcribe(audio_path, language="es")
    segmentos = []
    for segment in segments:
        segmentos.append({
            "inicio": segment.start,
            "fin": segment.end,
            "texto": segment.text.strip()
        })
    print(f"✅ {len(segmentos)} segmentos transcritos")
    return segmentos

def crear_imagen_subtitulo(texto, ancho=1080, alto=1920):
    """Crea una imagen transparente con el texto del subtítulo."""
    img = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Buscar fuente disponible
    font_paths = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/SFNSDisplay.ttf",
        "/System/Library/Fonts/SFNS.ttf",
    ]
    
    font = None
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, 50)
                break
            except:
                continue
    
    if font is None:
        font = ImageFont.load_default()
    
    # Wrap texto en múltiples líneas
    palabras = texto.split()
    lineas = []
    linea_actual = []
    for palabra in palabras:
        linea_actual.append(palabra)
        test = " ".join(linea_actual)
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] > ancho - 80:
            if len(linea_actual) > 1:
                linea_actual.pop()
                lineas.append(" ".join(linea_actual))
                linea_actual = [palabra]
            else:
                lineas.append(test)
                linea_actual = []
    if linea_actual:
        lineas.append(" ".join(linea_actual))
    
    texto_final = "\n".join(lineas)
    
    # Calcular posición (75% del alto)
    bbox = draw.textbbox((0, 0), texto_final, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (ancho - text_w) // 2
    y = int(alto * 0.75)
    
    # Sombra negra
    for dx, dy in [(-2,-2),(2,-2),(-2,2),(2,2),(0,2),(0,-2),(2,0),(-2,0)]:
        draw.text((x+dx, y+dy), texto_final, font=font, fill=(0, 0, 0, 220), align="center")
    
    # Texto blanco
    draw.text((x, y), texto_final, font=font, fill=(255, 255, 255, 255), align="center")
    
    return np.array(img)

def agregar_subtitulos(video_path, audio_path, output_path):
    segmentos = transcribir_audio(audio_path)
    
    print("⏳ Cargando video...")
    video = VideoFileClip(video_path)
    
    print("⏳ Generando subtítulos...")
    clips_subtitulos = []
    
    for seg in segmentos:
        if not seg["texto"]:
            continue
        try:
            img_array = crear_imagen_subtitulo(seg["texto"])
            clip = ImageClip(img_array, ismask=False)
            clip = clip.set_start(seg["inicio"])
            clip = clip.set_end(seg["fin"])
            clip = clip.set_duration(seg["fin"] - seg["inicio"])
            clips_subtitulos.append(clip)
        except Exception as e:
            print(f"  ⚠️ Error: {e}")
    
    print(f"✅ {len(clips_subtitulos)} subtítulos generados")
    
    print("⏳ Combinando video con subtítulos...")
    video_final = CompositeVideoClip([video] + clips_subtitulos)
    
    print("⏳ Exportando...")
    video_final.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        verbose=False,
        logger=None
    )
    
    print(f"✅ Video con subtítulos: {output_path}")
    return output_path

if __name__ == "__main__":
    agregar_subtitulos(
        video_path="videos_output/final/video_ken_burns.mp4",
        audio_path="videos_output/audio/narration.mp3",
        output_path="videos_output/final/video_subtitulos.mp4"
    )
