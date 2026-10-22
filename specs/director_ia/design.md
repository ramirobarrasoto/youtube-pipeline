# Diseño — director_ia

Complementa `requirements.md`. Apoyado en `docs/architecture.md` y `docs/conventions.md`.

## Archivos
| Archivo | Cambio |
|---|---|
| `scripts/director.py` | **Nuevo.** Todo el plan de escenas. |
| `scripts/generar_imagenes.py` | Nuevo parámetro opcional `prompts=None`. Sin otros cambios. |
| `app/app.py` | `run_pipeline`: llamar a `preparar_plan` y pasar los prompts (generación inicial y regeneración). No tocar `run_pipeline_multiidioma`. |
| `tests/__init__.py`, `tests/test_director.py`, `tests/test_generar_imagenes.py` | **Nuevos.** |

No se añaden dependencias.

## Firmas (`scripts/director.py`)
```python
VERSION_PLAN = 1
ESTILO_POR_DEFECTO = "cinematic, dramatic"

def dividir_en_oraciones(script: str) -> list[str]
def repartir_escenas(oraciones: list[str], cantidad: int) -> list[str]
def generar_plan(script, perfil, cantidad_escenas, llamar_llm=None) -> dict
def guardar_plan(plan: dict, ruta: str) -> None
def preparar_plan(script, perfil, cantidad_escenas, base_dir, llamar_llm=None) -> list[str]
```
Funciones privadas: `_construir_solicitud(escenas, estilo)`, `_extraer_json(texto)`, `_llamar_nvidia(mensajes)`, `_prompt_respaldo(texto, estilo)`.

## Decisiones
1. **El LLM solo escribe prompts de imagen.** El `texto` de cada escena sale de dividir el guion aprobado. Así el plan siempre cubre todo el guion (R6) y el LLM no puede omitir ni reescribir la narración.
2. **División en oraciones** con una expresión regular sobre `(?<=[.!?…])\s+`. Limitación conocida: abreviaturas tipo "Sr." o "etc." se partirán; aceptable para guiones narrados.
3. **Reparto en escenas:** agrupar oraciones consecutivas en `cantidad` grupos de longitud (en caracteres) lo más pareja posible, con al menos una oración por grupo. Si hay menos oraciones que escenas, una escena por oración (R5).
4. **Llamada al LLM inyectable.** `generar_plan` recibe `llamar_llm` (función `mensajes -> str`). Por defecto usa `_llamar_nvidia`, que replica la configuración de `generar_script.py`: URL `https://integrate.api.nvidia.com/v1/chat/completions`, modelo `moonshotai/kimi-k2.6`, clave en `NVIDIA_API_KEY`, `temperature` 0.7, `timeout` 120 s, `max_tokens` 1024. Los tests pasan un doble y nunca tocan la red.
5. **Formato de solicitud al LLM** (en inglés): rol de director visual; una lista numerada de escenas con su texto; pedir un prompt de imagen por escena, en inglés, máximo 30 palabras, sin texto ni letras dentro de la imagen, composición vertical, incluyendo el estilo del perfil; responder **solo** con `{"prompts": ["...", ...]}` con exactamente N elementos.
6. **Extracción del JSON.** Kimi puede devolver razonamiento antes del JSON (por eso existe `limpiar_razonamiento` en `generar_script.py`). `_extraer_json` busca el primer objeto JSON balanceado que contenga la clave `"prompts"`; si falla, devuelve `None` y se aplica el respaldo (R10).
7. **Estilo garantizado (R9).** Después de recibir un prompt del LLM, si no contiene el estilo del perfil, se le añade `", " + estilo`.
8. **Nunca se rompe el pipeline (R11).** Cualquier excepción del LLM se captura dentro de `generar_plan`; se registra con `print` (estilo del repo) y se usan los prompts de respaldo.
9. **`preparar_plan` es la única función que `app.py` necesita.** Hace `generar_plan` → `guardar_plan({base_dir}/plan.json)` → devuelve los prompts. Mantiene `app.py` casi sin lógica nueva.
10. **Integración en `run_pipeline`:** la cantidad de imágenes esperadas puede ser menor que `cantidad_imagenes` si el guion tiene pocas oraciones. Al construir la lista `imagenes` para el punto de aprobación, usar la lista que devuelve `generar_imagenes` en lugar de `range(cantidad_imagenes)`. La regeneración tras rechazo debe pasar los mismos `prompts`.

## Esquema de `plan.json`
```json
{
  "version": 1,
  "idioma": "es",
  "escenas": [
    {"id": 1, "texto": "…", "prompt_imagen": "…, vintage soccer, dramatic stadium, …"}
  ]
}
```

## Alternativas descartadas
- **Que el LLM divida el guion y devuelva texto + prompt.** Descartada: puede perder o alterar frases de la narración y el plan dejaría de cubrir el guion aprobado.
- **Refactorizar un cliente común de NVIDIA compartido con `generar_script.py`.** Descartada para esta feature: ampliaría el alcance y tocaría código sin tests. Queda anotada como mejora futura.
- **Integrar también el flujo multi-idioma.** Descartada: comparte imágenes entre idiomas; requiere decidir de qué idioma sale el plan. Se plantea aparte.

## Riesgos
- Que Pollinations ignore partes del prompt: se mitiga con prompts cortos y estilo siempre presente.
- Que el LLM tarde o falle: cubierto por R10 y R11.
- Que `run_pipeline` cambie de comportamiento al ajustar la lista de imágenes: revisión manual de Ramiro (R18).
