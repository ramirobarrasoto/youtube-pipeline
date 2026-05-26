"""
Pipeline de video completo:
1. Ken Burns sobre imágenes
2. Subtítulos sincronizados con audio
"""
import os
from generar_video import generar_video
from generar_subtitulos import agregar_subtitulos

def pipeline_video_completo(
    audio_path,
    images_dir,
    output_dir,
    con_subtitulos=True
):
    os.makedirs(output_dir, exist_ok=True)
    
    # PASO 1: Video con Ken Burns
    video_kenburns = os.path.join(output_dir, "video_kenburns.mp4")
    print("\n🎬 PASO 1: Aplicando efecto Ken Burns...")
    generar_video(
        audio_path=audio_path,
        images_dir=images_dir,
        output_path=video_kenburns
    )
    
    if not con_subtitulos:
        return video_kenburns
    
    # PASO 2: Agregar subtítulos
    video_final = os.path.join(output_dir, "video_final.mp4")
    print("\n📝 PASO 2: Agregando subtítulos...")
    agregar_subtitulos(
        video_path=video_kenburns,
        audio_path=audio_path,
        output_path=video_final
    )
    
    # Limpiar video intermedio
    if os.path.exists(video_kenburns):
        os.remove(video_kenburns)
        print("🧹 Video intermedio eliminado")
    
    print(f"\n✅ Video final listo: {video_final}")
    return video_final

if __name__ == "__main__":
    pipeline_video_completo(
        audio_path="videos_output/audio/narration.mp3",
        images_dir="videos_output/images",
        output_dir="videos_output/final"
    )
