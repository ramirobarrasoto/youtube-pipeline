# Cómo se escriben las specs (SDD)

Flujo: `pending → spec_author → spec_ready → ⏸ aprobación humana → in_progress → implementer → reviewer → done`.
Las features con `"sdd": false` saltan la spec: van de `pending` a `in_progress` y se guían por sus criterios de `acceptance`.

## Estados
| Estado | Significado |
|---|---|
| `pending` | Sin spec (o sin empezar). |
| `spec_ready` | Spec redactada. **Esperando aprobación humana; no se toca código.** |
| `in_progress` | Spec aprobada (o feature sin spec iniciada). Máximo una a la vez. |
| `done` | Implementada, con tests en verde y aprobada por el revisor. |
| `blocked` | Atascada; la razón está en `progress/`. |

## Archivos de una feature (`specs/<feature>/`)
- `requirements.md`: **qué** debe cumplirse, en formato EARS.
- `design.md`: **cómo** se construirá: archivos, firmas, decisiones, alternativa descartada, riesgos.
- `tasks.md`: pasos ordenados `- [ ] **T<n>**`, cada uno con los `R<n>` que cubre.

## EARS
Cada requisito es un párrafo con id estable (`R1`, `R2`…) y **un solo** `DEBE` o `NO DEBE`. Patrones:

| Patrón | Plantilla |
|---|---|
| Ubicuo | `El sistema DEBE <acción>.` |
| Evento | `CUANDO <disparador>, el sistema DEBE <acción>.` |
| Estado | `MIENTRAS <estado>, el sistema DEBE <acción>.` |
| Opcional | `DONDE <característica opcional>, el sistema DEBE <acción>.` |
| No deseado | `SI <situación no deseada> ENTONCES el sistema DEBE <acción>.` |

Reglas:
- Cada requisito debe poder verificarse con un test concreto. Si solo puede comprobarlo una persona, se marca `[manual]` y se explica cómo.
- Sin verbos blandos ("podría", "puede", "soporta").
- Si hay dos acciones, son dos requisitos.
- Los supuestos se listan aparte, al inicio, para que el humano los confirme.

## Nivel de detalle
Mucho contexto sobre objetivo, alcance y restricciones; poco sobre detalles que el implementador puede decidir solo (nombres de variables internas, orden de imports).

## Aprobación
El humano lee `specs/<feature>/`, pide cambios o aprueba con `./run-feature.sh aprobar <feature>`. Los cambios de spec se piden al agente `spec_author` (o se conversan en Claude) para mantener los tres archivos sincronizados.
