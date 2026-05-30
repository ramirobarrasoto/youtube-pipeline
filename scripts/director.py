"""
Director IA — genera un Plan de Producción completo en JSON.

El plan incluye el guión dividido en escenas con texto narrado,
query de imagen específica por escena, timings aproximados y tono musical.
"""
import os
import json
import time
import re
import copy
import requests
from dotenv import load_dotenv

load_dotenv("config/.env")

DURACIONES = {
    "corto": {"texto": "60-90 segundos",  "escenas": 5,  "seg": 75},
    "medio": {"texto": "3-5 minutos",     "escenas": 10, "seg": 240},
    "largo": {"texto": "8-10 minutos",    "escenas": 16, "seg": 540},
}

_PROMPT = """\
Eres el director creativo de un canal de YouTube llamado "{estilo}".
Crea un Plan de Producción para un video sobre: {tema}

Duración objetivo: {duracion_texto}

Devuelve ÚNICAMENTE un JSON válido con esta estructura (sin texto antes ni después):

{{
  "tema": "{tema}",
  "tono": "descripción del tono (ej: épico y dramático)",
  "musica": "epico",
  "escenas": [
    {{
      "id": 1,
      "inicio": 0.0,
      "fin": 15.0,
      "narracion": "Texto exacto en español que se narrará en esta escena.",
      "imagen_query": "specific English query to find the image (visual, concrete)",
      "fuente": "wikimedia",
      "transicion": "fade_in"
    }}
  ]
}}

Reglas:
1. La narración de TODAS las escenas concatenadas debe durar {duracion_texto} en voz alta
2. Cada escena dura entre 10 y 30 segundos
3. Narración en español, fluida y emotiva
4. imagen_query en inglés, específica y visual (ej: "Estadio Centenario Montevideo 1930 crowd")
5. fuente: "wikimedia" si es contenido histórico/real, "ia" si es conceptual/abstracto
6. transicion: "fade_in" primera escena, "corte" para las demás
7. musica: "epico", "dramatico", "aventura" o "sin_musica"
8. Genera exactamente {num_escenas} escenas
9. JSON válido, sin comentarios, sin texto adicional

Devuelve SOLO el JSON."""


def _extraer_json(texto: str) -> dict:
    try:
        return json.loads(texto.strip())
    except json.JSONDecodeError:
        pass

    m = re.search(r"```(?:json)?\s*([\s\S]+?)```", texto)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    inicio = texto.find("{")
    if inicio >= 0:
        depth = 0
        for i, c in enumerate(texto[inicio:], inicio):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(texto[inicio : i + 1])
                    except json.JSONDecodeError:
                        break

    raise ValueError("No se encontró JSON válido en la respuesta del Director IA")


def _normalizar_timings(plan: dict, duracion_total: float) -> dict:
    escenas = plan.get("escenas", [])
    if not escenas:
        return plan

    max_fin = max(e.get("fin", 0) for e in escenas)

    if max_fin <= 0 or max_fin > duracion_total * 3:
        seg = duracion_total / len(escenas)
        for i, e in enumerate(escenas):
            e["inicio"] = round(i * seg, 1)
            e["fin"] = round((i + 1) * seg, 1)
    else:
        factor = duracion_total / max_fin
        for e in escenas:
            e["inicio"] = round(e.get("inicio", 0) * factor, 1)
            e["fin"] = round(e.get("fin", 0) * factor, 1)

    for i, e in enumerate(escenas):
        e["id"] = i + 1

    plan["escenas"] = escenas
    return plan


def generar_plan(
    tema: str,
    duracion: str = "corto",
    estilo: str = "",
    sistema: str = None,
    intentos: int = 3,
) -> dict:
    """
    Genera el Plan de Producción completo usando Kimi K2.6.

    Returns:
        Dict con claves: tema, tono, musica, escenas[]
    """
    info = DURACIONES.get(duracion, DURACIONES["corto"])

    prompt = _PROMPT.format(
        tema=tema,
        duracion_texto=info["texto"],
        estilo=estilo or "cinematográfico, dramático, histórico",
        num_escenas=info["escenas"],
    )

    for intento in range(intentos):
        try:
            print(f"  Director IA — intento {intento + 1}/{intentos}...")
            resp = requests.post(
                url="https://integrate.api.nvidia.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('NVIDIA_API_KEY')}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "moonshotai/kimi-k2.6",
                    "stream": False,
                    "temperature": 0.7,
                    "messages": [
                        {
                            "role": "system",
                            "content": sistema
                            or "Eres un director creativo de YouTube. Respondes únicamente con JSON válido.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 4096,
                },
                timeout=180,
            )
            data = resp.json()
            texto = data["choices"][0]["message"]["content"]
            plan = _extraer_json(texto)

            if "escenas" not in plan or not plan["escenas"]:
                print("  Plan sin escenas, reintentando...")
                time.sleep(5)
                continue

            plan = _normalizar_timings(plan, info["seg"])
            print(
                f"  ✅ Plan generado: {len(plan['escenas'])} escenas, "
                f"tono: {plan.get('tono', 'N/A')}"
            )
            return plan

        except Exception as exc:
            print(f"  Error Director IA: {exc}")
            if intento < intentos - 1:
                print("  Reintentando en 10 segundos...")
                time.sleep(10)

    raise Exception("No se pudo generar el Plan de Producción después de 3 intentos")


def reescalar_timings(plan: dict, duracion_real: float) -> dict:
    """
    Reescala los timings del plan a la duración real del audio generado.
    Llamar después de generar el audio para sincronizar imagen ↔ narración.
    """
    plan = copy.deepcopy(plan)
    escenas = plan.get("escenas", [])
    if not escenas:
        return plan

    duracion_plan = max(e.get("fin", 0) for e in escenas)
    if duracion_plan <= 0:
        return plan

    factor = duracion_real / duracion_plan
    for e in escenas:
        e["inicio"] = round(e.get("inicio", 0) * factor, 1)
        e["fin"] = round(e.get("fin", 0) * factor, 1)

    plan["escenas"] = escenas
    return plan


def plan_a_script(plan: dict) -> str:
    """Concatena la narración de todas las escenas en un único texto."""
    return "\n\n".join(
        e.get("narracion", "").strip()
        for e in plan.get("escenas", [])
        if e.get("narracion")
    )


def plan_a_queries(plan: dict) -> list[str]:
    """Extrae la lista de imagen_query de cada escena."""
    return [e.get("imagen_query", "") for e in plan.get("escenas", []) if e.get("imagen_query")]


if __name__ == "__main__":
    tema = input("Tema:\n> ").strip()
    plan = generar_plan(tema, duracion="corto")
    print("\n" + "=" * 60)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    print("=" * 60)
    print("\nScript completo:")
    print(plan_a_script(plan))
