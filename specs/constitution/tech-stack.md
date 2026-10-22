# Stack técnico

> Reconstruido leyendo el código el 22-oct-2026. Lo marcado "no usado" se verificó con búsqueda en el repo.

## Lenguaje y ejecución
- Python 3 (versión exacta no fijada en el repo). Entorno virtual `venv/` (ignorado por git).
- App web local Flask (`app/app.py`, puerto 5000) con hilos (`threading`) y estado global para los puntos de aprobación. Plantilla: `app/templates/index.html`.
- Scripts en `scripts/`, importados por la app mediante `sys.path`.

## Servicios y librerías por etapa
| Etapa | Implementación | Archivo |
|---|---|---|
| Guion | API de NVIDIA (`integrate.api.nvidia.com`), modelo `moonshotai/kimi-k2.6`, vía `requests`; variable `NVIDIA_API_KEY` | `scripts/generar_script.py` |
| Audio | `edge-tts` (voces Microsoft Neural) | `scripts/generar_audio.py` |
| Imágenes | Pollinations.ai (`image.pollinations.ai`), 1080x1920, `requests` + Pillow | `scripts/generar_imagenes.py` |
| Video | MoviePy 1.0.3, efecto Ken Burns, duración igual para todas las imágenes | `scripts/generar_video.py` |
| Subtítulos | `faster-whisper` modelo `base` (CPU, int8), superpuestos con MoviePy | `scripts/generar_subtitulos.py` |
| Miniatura | Pollinations.ai, 1280x720 | `scripts/generar_thumbnail.py` |
| Subida | YouTube Data API v3 (`google-api-python-client`, OAuth) | `scripts/subir_youtube.py` |

## Configuración y secretos
- `config/.env` y `config/*.json|*.pickle` están en `.gitignore`. No se encontraron secretos en el repo.
- Variables usadas: `NVIDIA_API_KEY`, `YOUTUBE_CREDENTIALS`.
- Cada perfil (`perfiles/*.json`) define `nombre`, `idioma`, `env_file`, `youtube_token`, `voz_default`, `estilo_imagenes`, `tags`, `prompt_sistema`. Los perfiles sin sufijo de idioma (`futbol.json`, `cuentos.json`, `biografias.json`) son versiones antiguas, más cortas.

## Deuda técnica observada (verificada en el código)
1. `requirements.txt` **no incluye** Flask, edge-tts, faster-whisper ni numpy, que el código importa. Sí incluye `anthropic` y `elevenlabs`, que ningún archivo usa.
2. `generar_audio.py`: el diccionario `VOCES` solo tiene 3 voces en español. Los perfiles en/pt pasan su `voz_default` (ej. `pt-BR-FranciscaNeural`), que no está en `VOCES`, y cae a la voz en español "Carlos".
3. `generar_subtitulos.py`: `language="es"` fijo para Whisper, y solo busca fuentes de macOS.
4. `generar_thumbnail.py`: el prompt dice "vintage soccer" para todos los canales, incluidos cuentos y biografías.
5. `subir_youtube.py`: el token (`config/token.pickle`) y los tags (`fútbol, historia, mundiales, 2026`) están fijos; `youtube_token` y `tags` de cada perfil no se usan.
6. Las imágenes se generan con 8 plantillas fijas (`tema + estilo + variante`), sin relación con lo que narra cada parte, y duran todas lo mismo.
7. `arrancar.sh` usa una ruta fija `~/development/Proyectos/Youtube`.
8. No hay tests. El README está desactualizado.
9. La modalidad multi-idioma comparte imágenes entre idiomas y toma el estilo del perfil en español.

## Propuesto pero no implementado
- Fuentes reales de imágenes (Wikimedia Commons, Pexels) y sincronía audio-imagen: "Director IA" (`scripts/director.py` no existe todavía).
