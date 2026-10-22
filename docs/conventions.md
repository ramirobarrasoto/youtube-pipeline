# Convenciones

Observadas en el código existente. Seguirlas salvo que una spec indique otra cosa.

## Estilo
- Nombres de funciones y variables en `snake_case` y **en español** (`generar_script`, `cantidad_imagenes`).
- Docstrings y comentarios en español.
- Mensajes de progreso con `print` y emoji (`⏳`, `✅`, `⚠️`), como el resto de `scripts/`.
- Cada script puede ejecutarse solo con `if __name__ == "__main__":` para pruebas manuales.
- Indentación de 4 espacios; sin formateador impuesto.

## Errores
- Llamadas a servicios externos con reintentos y mensajes claros (patrón de `generar_script.py` e `generar_imagenes.py`).
- Una etapa opcional no debe romper el pipeline completo (ej. la miniatura devuelve `None` si falla).

## Tests
- Framework: `unittest` de la biblioteca estándar. Sin dependencias de test nuevas.
- Ubicación: `tests/test_<modulo>.py`. **No** crear `scripts/test_*.py` (está en `.gitignore`).
- Los scripts no son un paquete: el test añade `scripts/` al `sys.path` antes de importar.
- **Sin red, sin modelos, sin claves:** NVIDIA, Pollinations, YouTube, edge-tts y Whisper se sustituyen por dobles.
- Archivos temporales con `tempfile.TemporaryDirectory()`.
- No importar `moviepy` ni `faster_whisper` desde tests nuevos si no hace falta.

## Seguridad
- Nunca leer, imprimir, copiar a logs ni commitear `config/` o archivos `.env`.
- No introducir claves ni tokens en el código.

## Dependencias
- No añadir dependencias sin que la spec lo indique. Si se añade una, declararla en `requirements.txt`.
