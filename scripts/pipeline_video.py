"""
Pipeline de video completo:
  1. Ken Burns sobre imágenes
  2. Subtítulos sincronizados con audio
  3. Música de fondo épica (opcional)

Géneros disponibles: "epico", "dramatico", "aventura", "sin_musica" (default)
"""
import os
import shutil
from generar_video import generar_video
from generar_subtitulos import agregar_subtitulos


# ─────────────────────────────────────────────────────────────────────────────
# Paso 3 — Música de fondo
# ─────────────────────────────────────────────────────────────────────────────

def agregar_musica_al_video(
    video_path: str,
    genero_musica: str,
    output_path: str,
    volumen: float = 0.25,
) -> bool:
    """
    Mezcla música de fondo con el video en video_path.
    El resultado se escribe en output_path.
    Si falla, copia video_path → output_path y devuelve False.

    Args:
        video_path:    Ruta al video de entrada.
        genero_musica: Género para descargar/usar (ej. "epico").
        output_path:   Ruta del video resultante.
        volumen:       Nivel de volumen de la música (0.0-1.0).

    Returns:
        True si se mezcló la música; False si se usó fallback (sin música).
    """
    try:
        from descargar_musica import obtener_musica
        music_path = obtener_musica(genero_musica)

        if not music_path:
            print("  ⚠️  No se obtuvo música; se continúa sin ella")
            if not os.path.exists(output_path):
                shutil.copy2(video_path, output_path)
            return False

        from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
        import moviepy.audio.fx.all as afx

        print("  🎬  Mezclando música con video...")
        video    = VideoFileClip(video_path)
        duracion = video.duration

        musica = AudioFileClip(music_path)

        # Loopear si la pista es más corta que el video
        if musica.duration < duracion:
            musica = musica.fx(afx.audio_loop, duration=duracion)
        else:
            musica = musica.subclip(0, duracion)

        # Fade-out en los últimos 3 s (o 10% de la duración)
        fade_dur = min(3.0, duracion * 0.10)
        musica   = musica.fx(afx.audio_fadeout, fade_dur)

        # Ajustar volumen
        musica = musica.volumex(volumen)

        # Mezclar con narración original
        audio_original = video.audio
        audio_final    = (
            CompositeAudioClip([audio_original, musica])
            if audio_original
            else musica
        )

        (
            video.set_audio(audio_final)
            .write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                verbose=False,
                logger=None,
            )
        )

        video.close()
        musica.close()
        print(f"  ✅  Música añadida (volumen: {int(volumen * 100)}%)")
        return True

    except Exception as exc:
        print(f"  ❌  Error al agregar música: {exc}")
        import traceback
        traceback.print_exc()
        if not os.path.exists(output_path):
            shutil.copy2(video_path, output_path)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Función principal del pipeline
# ─────────────────────────────────────────────────────────────────────────────

def pipeline_video_completo(
    audio_path: str,
    images_dir: str,
    output_dir: str,
    con_subtitulos: bool = True,
    genero_musica: str | None = None,
    plan_produccion: dict | None = None,
) -> str:
    """
    Ejecuta el pipeline completo:
      PASO 1 → Ken Burns
      PASO 2 → Subtítulos  (si con_subtitulos=True)
      PASO 3 → Música      (si genero_musica no es None/"sin_musica")

    Returns:
        Ruta al video_final.mp4.
    """
    os.makedirs(output_dir, exist_ok=True)

    usar_musica = bool(genero_musica and genero_musica != "sin_musica")

    # Rutas de archivos intermedios
    video_kenburns = os.path.join(output_dir, "video_kenburns.mp4")
    video_subs     = os.path.join(output_dir, "video_subs.mp4")
    video_final    = os.path.join(output_dir, "video_final.mp4")

    # ── PASO 1: Ken Burns ─────────────────────────────────────────────────
    print("\n🎬  PASO 1: Aplicando efecto Ken Burns...")
    generar_video(
        audio_path=audio_path,
        images_dir=images_dir,
        output_path=video_kenburns,
        plan_produccion=plan_produccion,
    )

    # ── Rama sin subtítulos ────────────────────────────────────────────────
    if not con_subtitulos:
        if usar_musica:
            print(f"\n🎵  PASO 2: Agregando música de fondo ({genero_musica})...")
            agregar_musica_al_video(video_kenburns, genero_musica, video_final)
            if os.path.exists(video_kenburns):
                os.remove(video_kenburns)
                print("🧹  Video Ken Burns intermedio eliminado")
            print(f"\n✅  Video final listo: {video_final}")
            return video_final
        print(f"\n✅  Video listo (sin subtítulos ni música): {video_kenburns}")
        return video_kenburns

    # ── PASO 2: Subtítulos ────────────────────────────────────────────────
    # Si hay música, los subtítulos van a un temporal para no pisar video_final
    subs_dest = video_subs if usar_musica else video_final

    print("\n📝  PASO 2: Agregando subtítulos...")
    agregar_subtitulos(
        video_path=video_kenburns,
        audio_path=audio_path,
        output_path=subs_dest,
    )

    if os.path.exists(video_kenburns):
        os.remove(video_kenburns)
        print("🧹  Video Ken Burns intermedio eliminado")

    # Sin música: ya está listo
    if not usar_musica:
        print(f"\n✅  Video final listo: {video_final}")
        return video_final

    # ── PASO 3: Música de fondo ───────────────────────────────────────────
    print(f"\n🎵  PASO 3: Agregando música de fondo ({genero_musica})...")
    agregar_musica_al_video(video_subs, genero_musica, video_final, volumen=0.25)

    if os.path.exists(video_subs):
        os.remove(video_subs)
        print("🧹  Video intermedio de subtítulos eliminado")

    print(f"\n✅  Video final listo: {video_final}")
    return video_final


# ─────────────────────────────────────────────────────────────────────────────
# CLI rápido para testing
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    pipeline_video_completo(
        audio_path="videos_output/audio/narration.mp3",
        images_dir="videos_output/images",
        output_dir="videos_output/final",
        genero_musica="epico",
    )
