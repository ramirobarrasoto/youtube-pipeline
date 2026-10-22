# Tareas — director_ia

Orden obligatorio. Marcar `[x]` al terminar cada una. Cada tarea que añade código lleva sus tests en el mismo paso. Los tests no llaman a la red.

- [ ] **T1** Crear `scripts/director.py` con `dividir_en_oraciones` y `repartir_escenas`, y `tests/__init__.py` + `tests/test_director.py` con sus tests (incluye añadir `scripts/` al `sys.path` en el test). Cubre: R4, R5, R6.
- [ ] **T2** Añadir `_construir_solicitud`, `_extraer_json` y `_prompt_respaldo`, con tests (JSON limpio, JSON precedido de razonamiento, texto sin JSON). Cubre: R8, R10.
- [ ] **T3** Añadir `generar_plan` con `llamar_llm` inyectable, normalización del estilo y respaldo ante error, con tests usando un LLM falso. Cubre: R1, R2, R3, R7, R9, R10, R11, R12, R13.
- [ ] **T4** Añadir `_llamar_nvidia`, `guardar_plan` y `preparar_plan`, con tests (usar `tempfile.TemporaryDirectory`; `_llamar_nvidia` no se prueba contra la red). Cubre: R14, R15.
- [ ] **T5** Modificar `generar_imagenes(…, prompts=None)` en `scripts/generar_imagenes.py` y crear `tests/test_generar_imagenes.py` (sustituir `generar_imagen_con_reintento` por un doble que registre los prompts). Cubre: R16, R17.
- [ ] **T6** Integrar en `run_pipeline` de `app/app.py` según el diseño (punto 10) y comprobar con `python3 -m py_compile app/app.py`. **Verificación manual de Ramiro:** generar un video corto de un canal y comprobar que existe `plan.json` en la carpeta del video y que las imágenes siguen el guion. Cubre: R18 `[manual]`.
- [ ] **T7** Ejecutar `./init.sh` hasta que termine en verde y escribir `progress/impl_director_ia.md` con el mapa `R<n> → test` y las desviaciones, si las hubo.
