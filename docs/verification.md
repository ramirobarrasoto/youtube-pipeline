# Verificación

## Qué comprueba `./init.sh`
1. Entorno: `python3` disponible.
2. Archivos base del arnés presentes.
3. `feature_list.json` válido: estados permitidos, máximo una feature `in_progress`, y spec completa para toda feature `sdd` en `spec_ready`, `in_progress` o `done`.
4. **Sintaxis** de todos los `.py` de `scripts/`, `app/` y `tests/` (`py_compile`; no requiere instalar dependencias).
5. **Tests** (`unittest`) si existen archivos `tests/test_*.py`. Requieren `pip install -r requirements.txt`.

`./init.sh` debe terminar con código 0 antes de cerrar cualquier feature.

## Checkpoints del revisor
- **C1 — Spec respetada:** cada `R<n>` automatizable tiene un test concreto; las tareas están `[x]`; no hay cambios fuera del diseño.
- **C2 — Verificación real:** los tests pasan con `unittest`, no llaman a red/modelos/claves y usan archivos temporales.
- **C3 — Convenciones:** estilo del repo, sin dependencias nuevas no previstas, sin `print` de depuración sueltos.
- **C4 — Seguridad:** no se tocó `config/` ni `.env`; no hay claves en el código ni en los logs.
- **C5 — Estado y cierre:** `progress/impl_<feature>.md` existe con el mapa `R<n> → test`; `feature_list.json` coherente (una sola feature `in_progress`).
- **C6 — Pendientes humanos:** los requisitos `[manual]` están listados con instrucciones de comprobación.

## Verificación manual (la hace Ramiro)
Lo que la app no permite probar sin ejecutarla (hilos, interfaz, servicios reales) se prueba con una corrida corta de un canal y se anota en `progress/history.md`.
