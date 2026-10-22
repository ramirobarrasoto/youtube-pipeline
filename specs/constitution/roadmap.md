# Roadmap

> Borrador. Los nombres coinciden con `feature_list.json`. Orden pensado para el piloto: primero lo pequeño y contenido, luego lo que toca el render o la subida.

## Piloto SDD (3 features)
1. `requirements_baseline` (sin spec, `"sdd": false`): añadir a `requirements.txt` las dependencias que el código usa y falta declarar. No se elimina nada todavía.
2. `director_ia` (con spec: `specs/director_ia/`): plan de escenas con un prompt de imagen por fragmento del guion, para sustituir las 8 plantillas fijas.
3. `voces_por_idioma`: que cada perfil use su `voz_default` en lugar de caer a la voz en español.

## Después del piloto
4. `sincronia_escenas`: la duración de cada imagen proporcional al texto de su escena (continúa `director_ia`).
5. `subtitulos_por_idioma`: idioma de Whisper según el perfil y fuentes que no dependan de macOS.
6. `thumbnail_por_perfil`: miniatura con el estilo del perfil, sin "soccer" fijo.
7. `youtube_por_perfil` (riesgo alto: publica en canales): token y tags del perfil.
8. `director_fuentes_reales` (complejo): Wikimedia Commons / Pexels como alternativa a imágenes generadas.
9. `limpieza_dependencias`: retirar `anthropic` y `elevenlabs` si siguen sin usarse (confirmar con Ramiro).

## Criterio de orden
Riesgo creciente: tareas triviales sin spec, features con spec que no tocan la subida, y por último lo que publica en YouTube o añade servicios externos.
