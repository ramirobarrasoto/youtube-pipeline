# Arquitectura

## Estructura del repo
```
app/app.py                 Flask: rutas, hilo del pipeline, puntos de aprobación (estado global)
app/templates/index.html   Interfaz web
scripts/                   Una etapa del pipeline por archivo
perfiles/*.json            Un perfil por canal e idioma (+3 perfiles antiguos sin sufijo)
config/                    (ignorado por git) .env, credenciales y tokens
videos_output/             (ignorado por git) resultados por canal y tema
specs/                     Constitución y specs de features
tests/                     Tests unittest
```

## Flujo de un canal (`run_pipeline`)
1. Cargar `perfiles/<canal>.json` y su `env_file`.
2. `generar_script` → **aprobación del guion**.
3. `generar_audio` → **aprobación del audio**.
4. `generar_imagenes` → **aprobación de imágenes**.
5. `pipeline_video_completo` (Ken Burns + subtítulos con Whisper).
6. `generar_thumbnail`.
7. `subir_video` (privado por defecto) y `metadata.json`.

Flujo multi-idioma (`run_pipeline_multiidioma`): mismos pasos para es/en/pt con imágenes compartidas.

## Reglas de dependencia
- `scripts/*.py` no importan `app/`. La app importa los scripts (añade `scripts/` a `sys.path`).
- Los scripts leen configuración con `python-dotenv` desde `config/.env`.
- Las rutas de salida se construyen relativas a `BASE_DIR` o al directorio de trabajo; no añadir rutas absolutas nuevas.
- Un script nuevo expone funciones puras o con dependencias inyectables; el acceso a red va en funciones pequeñas que se puedan sustituir en los tests.
