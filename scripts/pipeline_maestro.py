import os
import sys
from dotenv import load_dotenv

load_dotenv("config/.env")

# Importar todos los módulos
sys.path.append("scripts")
from generar_script import generar_script
from generar_audio import generar_audio
from generar_video import generar_video
from generar_thumbnail import generar_thumbnail
from subir_youtube import subir_video

def pipeline_completo(tema: str):
    print("\n" + "="*60)
    print(f"🚀 PIPELINE INICIADO")
    print(f"📝 Tema: {tema}")
    print("="*60 + "\n")
    
    # Crear carpeta para este video
    nombre_carpeta = tema[:30].replace(" ", "_").replace("/", "-")
    base_dir = f"videos_output/{nombre_carpeta}"
    os.makedirs(f"{base_dir}/images", exist_ok=True)
    
    # PASO 1: Generar Script
    print("📝 PASO 1/5: Generando script...")
    script = generar_script(tema)
    script_path = f"{base_dir}/script.txt"
    with open(script_path, "w") as f:
        f.write(script)
    print(f"✅ Script listo\n")
    
    # PASO 2: Generar Audio
    print("🎙️ PASO 2/5: Generando audio...")
    audio_path = generar_audio(
        script=script,
        nombre_archivo=f"{base_dir}/narration.mp3"
    )
    print(f"✅ Audio listo\n")
    
    # PASO 3: Generar Imágenes
    print("🖼️ PASO 3/5: Generando imágenes...")
    from generar_imagenes import generar_imagenes
    generar_imagenes(tema, output_dir=f"{base_dir}/images")
    print(f"✅ Imágenes listas\n")
    
    # PASO 4: Compilar Video
    print("🎬 PASO 4/5: Compilando video...")
    video_path = generar_video(
        audio_path=audio_path,
        images_dir=f"{base_dir}/images",
        output_path=f"{base_dir}/video_final.mp4"
    )
    print(f"✅ Video listo\n")
    
    # PASO 5: Generar Thumbnail + Subir
    print("📤 PASO 5/5: Generando thumbnail y subiendo a YouTube...")
    thumbnail_path = generar_thumbnail(
        tema=tema,
        output_path=f"{base_dir}/thumbnail.jpg"
    )
    
    url = subir_video(
        video_path=video_path,
        titulo=tema,
        descripcion=f"""{script[:200]}...

Suscríbete a Historias Mundialistas para más contenido épico.

#Fútbol #Historia #Mundiales #HistoriasMundialistas""",
        thumbnail_path=thumbnail_path,
        privacidad="private"
    )
    
    print("\n" + "="*60)
    print("🎉 PIPELINE COMPLETADO!")
    print(f"🔗 Video en YouTube: {url}")
    print(f"👁️  Estado: PRIVADO - revisá antes de publicar")
    print("="*60 + "\n")
    
    return url

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Desde terminal: python pipeline_maestro.py "Mi tema"
        tema = " ".join(sys.argv[1:])
    else:
        # Interactivo
        tema = input("📝 Ingresa el tema del video:\n> ").strip()
    
    pipeline_completo(tema)
