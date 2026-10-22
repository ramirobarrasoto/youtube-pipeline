# Requisitos — director_ia

Estado: **borrador a la espera de aprobación humana** (`spec_ready`).
Formato: EARS (ver `docs/specs.md`). Cada requisito tiene un solo `DEBE` y lo verifica un test, salvo los marcados `[manual]`.

## Objetivo
Hoy `generar_imagenes` crea las imágenes con 8 plantillas fijas (`tema + estilo + variante`), sin relación con lo que narra cada parte del guion. Esta feature añade un "director" que divide el guion en escenas y pide al LLM un prompt de imagen específico por escena, y hace que `generar_imagenes` pueda usarlos.

## Supuestos a confirmar por Ramiro
1. Los `prompt_imagen` se piden **en inglés** (Pollinations responde mejor), aunque el guion esté en es/pt.
2. El LLM es el mismo que usa `generar_script.py` (NVIDIA API, `moonshotai/kimi-k2.6`, `NVIDIA_API_KEY`).
3. **Alcance:** solo el flujo de un canal (`run_pipeline`). El flujo multi-idioma (`run_pipeline_multiidioma`) queda **sin cambios**.
4. **Fuera de alcance:** Wikimedia/Pexels, duración de cada imagen según su escena (feature `sincronia_escenas`), cambios en audio, subtítulos, miniatura y subida.
5. El texto de cada escena **no lo escribe el LLM**: se obtiene dividiendo el guion aprobado. El LLM solo escribe los prompts de imagen.

## Requisitos

### Plan de escenas (`scripts/director.py`)
**R1** CUANDO se invoca `generar_plan(script, perfil, cantidad_escenas)` con un `script` que tiene al menos una oración y `cantidad_escenas` ≥ 1, el sistema DEBE devolver un diccionario con las claves `version`, `idioma` y `escenas`.

**R2** El sistema DEBE asignar al campo `version` del plan el valor entero `1`.

**R3** El sistema DEBE asignar al campo `idioma` del plan el valor de `perfil["idioma"]`, o `"es"` cuando el perfil no define `idioma`.

**R4** El sistema DEBE dividir el guion en fragmentos consecutivos cuyos límites coincidan con el final de una oración, entendida como texto terminado en `.`, `!`, `?` o `…` seguido de espacio o de fin de texto.

**R5** El sistema DEBE devolver un número de escenas igual al menor entre `cantidad_escenas` y el número de oraciones del guion.

**R6** El sistema DEBE producir escenas cuyo `texto`, concatenado en orden y con los espacios en blanco normalizados, sea igual al guion con los espacios en blanco normalizados.

**R7** El sistema DEBE dar a cada escena un `id` entero consecutivo desde 1, un `texto` no vacío y un `prompt_imagen` no vacío.

### Prompts de imagen
**R8** CUANDO el sistema solicita los prompts al LLM, la solicitud DEBE incluir el `estilo_imagenes` del perfil y el `texto` de cada escena.

**R9** El sistema DEBE incluir el `estilo_imagenes` del perfil (o `"cinematic, dramatic"` si el perfil no lo define) dentro de cada `prompt_imagen` del plan devuelto.

**R10** SI la respuesta del LLM no contiene un JSON válido, o no trae un prompt no vacío para una escena, ENTONCES el sistema DEBE usar para esa escena el prompt de respaldo, formado por los primeros 120 caracteres de su `texto`, una coma y el estilo.

**R11** SI la llamada al LLM lanza una excepción o agota el tiempo de espera, ENTONCES el sistema NO DEBE propagar la excepción y DEBE devolver el plan completo con prompts de respaldo.

### Validación de entrada
**R12** SI el `script` está vacío o contiene solo espacios en blanco, ENTONCES `generar_plan` DEBE lanzar `ValueError`.

**R13** SI `cantidad_escenas` es menor que 1, ENTONCES `generar_plan` DEBE lanzar `ValueError`.

### Persistencia y orquestación
**R14** CUANDO se invoca `guardar_plan(plan, ruta)`, el sistema DEBE escribir el plan como JSON en UTF-8, con `ensure_ascii=False` e `indent=2`, creando los directorios intermedios que falten.

**R15** CUANDO se invoca `preparar_plan(script, perfil, cantidad_escenas, base_dir)`, el sistema DEBE guardar el plan en `{base_dir}/plan.json` y devolver la lista de `prompt_imagen` en el orden de las escenas.

### Generación de imágenes (`scripts/generar_imagenes.py`)
**R16** CUANDO `generar_imagenes` recibe el parámetro opcional `prompts` con al menos un elemento, el sistema DEBE generar una imagen por prompt, hasta un máximo de `cantidad`, usando cada prompt sin modificarlo.

**R17** CUANDO `generar_imagenes` se invoca sin `prompts`, el sistema DEBE usar las 8 plantillas internas actuales y producir los mismos prompts que antes de esta feature.

### Integración en la app (`app/app.py`)
**R18** `[manual]` CUANDO `run_pipeline` llega a la etapa de imágenes, el sistema DEBE llamar a `preparar_plan` y pasar los prompts resultantes a `generar_imagenes`, tanto en la generación inicial como en la regeneración tras un rechazo de Ramiro.

## Fuera de alcance de los tests
`app/app.py` no tiene tests y usa hilos y estado global. R18 lo verifica Ramiro a mano (ver `tasks.md`, T6) y el revisor comprueba el código con `python3 -m py_compile`.
