"""
Servicio Gemini — Generación de guión estructurado en JSON para videos largos.

Usa la Google Gemini API con salida JSON tipada (response_mime_type + response_schema)
para garantizar que cada escena del video tenga exactamente los campos necesarios.

Instalación:
    pip install google-genai

API Key gratuita (con límites generosos):
    https://aistudio.google.com/apikey  →  agregar GEMINI_API_KEY a config/.env

Modelo por defecto: gemini-2.5-flash
Si querés usar gemini-3.5-flash u otro, cambiá la constante GEMINI_MODEL abajo.
"""
import os
import json
import time
from dotenv import load_dotenv

load_dotenv("config/.env")

# ── Configuración ─────────────────────────────────────────────────────────────
# Cambiá este valor si querés usar otro modelo de Gemini
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Segundos por escena (4-6 para videos dinámicos)
SEGS_POR_ESCENA = 5

DURACIONES = {
    "corto": {"texto": "90 segundos",  "seg": 90},
    "medio": {"texto": "5 minutos",    "seg": 300},
    "largo": {"texto": "15 minutos",   "seg": 900},
}

# JSON Schema estricto para el array de escenas
_SCHEMA_ESCENAS = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "numero_escena":   {"type": "integer"},
            "texto_narracion": {"type": "string"},
            "prompt_visual_ia": {"type": "string"},
        },
        "required": ["numero_escena", "texto_narracion", "prompt_visual_ia"],
    },
}

_PROMPT_GUION = """\
Eres el director creativo de un canal de YouTube llamado "{canal}".
Vas a crear el guión completo de un video de {duracion_texto} sobre: "{tema}"
El video estará narrado en {idioma}.

Divide el video en escenas de exactamente {segs_por_escena} segundos cada una.
Para un video de {duracion_texto} necesitás aproximadamente {num_escenas} escenas.

Para cada escena devolvé:
- numero_escena: número secuencial (1, 2, 3...)
- texto_narracion: el texto EXACTO que se narrará en voz alta en {idioma}.
  Debe durar exactamente {segs_por_escena} segundos cuando se lee en voz alta
  (aprox. {palabras_por_escena} palabras). Sin notas al pie, sin aclaraciones.
- prompt_visual_ia: descripción en inglés hiper-detallada de la imagen para esta escena.
  Estilo: cinematográfico 4K, ultra-realista, iluminación dramática.
  Incluí: qué se ve, ángulo de cámara, paleta de colores, época histórica si aplica.
  Ejemplo: "Aerial view of Estadio Centenario in Montevideo 1930, packed with 90000 spectators,
  sepia tones, dramatic clouds, golden hour lighting, 4K cinematic"

Reglas críticas:
1. La narración debe ser fluida, emotiva y entretenida
2. Cada texto_narracion debe tener EXACTAMENTE {palabras_por_escena} palabras aprox.
3. prompt_visual_ia siempre en inglés, muy específico y visual
4. Secuencia narrativa coherente: introducción → desarrollo → climax → cierre
5. Devolvé SOLO el array JSON, sin texto adicional
"""


def _get_client():
    """Crea el cliente Gemini. Importa aquí para no fallar si no está instalado."""
    try:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY no está definida en config/.env")
        return genai.Client(api_key=api_key)
    except ImportError:
        raise ImportError(
            "SDK de Gemini no instalado. Ejecutá: pip install google-genai"
        )


def generar_guion_estructurado(
    canal: str,
    idioma: str,
    tema: str,
    duracion: str = "largo",
    intentos: int = 3,
) -> list[dict]:
    """
    Genera el guión completo como array de escenas usando Gemini con JSON Schema.

    Returns:
        Lista de dicts: [{numero_escena, texto_narracion, prompt_visual_ia}, ...]
        Para un video de 15 min → ~180 escenas de 5 segundos cada una.
    """
    from google.genai import types

    info = DURACIONES.get(duracion, DURACIONES["largo"])
    num_escenas = info["seg"] // SEGS_POR_ESCENA
    # ~3 palabras/segundo en español → 15 palabras por escena de 5s
    palabras_por_escena = SEGS_POR_ESCENA * 3

    prompt = _PROMPT_GUION.format(
        canal=canal,
        tema=tema,
        idioma=idioma,
        duracion_texto=info["texto"],
        segs_por_escena=SEGS_POR_ESCENA,
        num_escenas=num_escenas,
        palabras_por_escena=palabras_por_escena,
    )

    client = _get_client()

    for intento in range(intentos):
        try:
            print(f"  Gemini guión — intento {intento + 1}/{intentos} "
                  f"(~{num_escenas} escenas, modelo: {GEMINI_MODEL})...")

            # Usamos solo response_mime_type sin response_schema
            # El prompt ya instruye la estructura exacta — más compatible entre modelos
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                    max_output_tokens=65536,
                ),
            )

            texto = response.text
            if not texto or not texto.strip():
                print("  Respuesta vacía, reintentando...")
                time.sleep(5)
                continue

            escenas = json.loads(texto)

            if not isinstance(escenas, list) or len(escenas) == 0:
                print("  Respuesta no es un array válido, reintentando...")
                time.sleep(5)
                continue

            escenas = [
                e for e in escenas
                if e.get("texto_narracion") and e.get("prompt_visual_ia")
            ]

            if not escenas:
                print("  Escenas sin campos requeridos, reintentando...")
                time.sleep(5)
                continue

            print(f"  ✅ Guión generado: {len(escenas)} escenas "
                  f"(~{len(escenas) * SEGS_POR_ESCENA // 60} min {len(escenas) * SEGS_POR_ESCENA % 60}s)")
            return escenas

        except Exception as exc:
            import traceback
            print(f"  Error Gemini (intento {intento+1}): {exc}")
            print(f"  Detalle: {traceback.format_exc()[-500:]}")
            if intento < intentos - 1:
                print("  Reintentando en 10 segundos...")
                time.sleep(10)

    raise Exception(f"No se pudo generar el guión con Gemini después de {intentos} intentos")


def guion_a_script_completo(escenas: list[dict]) -> str:
    """Concatena toda la narración del guión en un único texto."""
    return "\n\n".join(
        e.get("texto_narracion", "").strip()
        for e in escenas
        if e.get("texto_narracion")
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI para testing
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tema = input("Tema:\n> ").strip()
    dur = input("Duración (corto/medio/largo) [largo]: ").strip() or "largo"
    escenas = generar_guion_estructurado(
        canal="Historia Épica",
        idioma="español",
        tema=tema,
        duracion=dur,
    )
    print(f"\n{'='*60}")
    print(f"Total escenas: {len(escenas)}")
    print(f"Duración estimada: {len(escenas) * SEGS_POR_ESCENA}s "
          f"({len(escenas) * SEGS_POR_ESCENA // 60}min)")
    print(f"\nPrimeras 3 escenas:")
    for e in escenas[:3]:
        print(f"\n  Escena {e['numero_escena']}:")
        print(f"  Narración: {e['texto_narracion'][:100]}...")
        print(f"  Visual: {e['prompt_visual_ia'][:80]}...")
    with open("/tmp/guion_gemini.json", "w") as f:
        json.dump(escenas, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Guión completo guardado en /tmp/guion_gemini.json")
