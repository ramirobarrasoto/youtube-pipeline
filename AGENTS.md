# AGENTS.md — Pipeline Maestro YouTube

Pipeline que genera videos verticales (1080x1920) para YouTube: 3 temáticas de canal × 3 idiomas (es/en/pt) = 9 perfiles. Este archivo es corto a propósito: el detalle vive en `specs/` y `docs/`.

## Dónde mirar
- Constitución del proyecto: `specs/constitution/` (misión, stack, roadmap)
- Estado de las features: `feature_list.json` · sesión activa: `progress/current.md`
- Convenciones, arquitectura y verificación: `docs/`
- Roles de los agentes: `.agents/agents/<rol>/agent.md`

## Comandos
- Verificar todo: `./init.sh`
- Tests: `python3 -m unittest discover -s tests -v` (requiere `pip install -r requirements.txt`)
- Orquestar una feature: `./run-feature.sh status`
- App local (macOS del autor): `./arrancar.sh`

## Reglas duras
1. Nada de código sin spec aprobada, salvo features con `"sdd": false` en `feature_list.json`.
2. Una feature a la vez y un agente a la vez.
3. Nunca leer, imprimir ni commitear `config/` ni archivos `.env` (credenciales).
4. No salir del alcance de la spec. Si no se puede cumplir, parar y pedir un cambio de spec; no improvisar.
5. Los agentes escriben sus resultados en archivos (`specs/`, `progress/`) y responden con UNA línea con la ruta.
6. No añadir dependencias que la spec no mencione.
7. Los tests viven en `tests/`. Nunca en `scripts/test_*.py` (está en `.gitignore`).
8. Los tests no llaman a APIs externas (NVIDIA, Pollinations, YouTube, Whisper): usar dobles.
9. Trabajar en una rama `feature/<nombre>`, nunca directamente en `main`.
