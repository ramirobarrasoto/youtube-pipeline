import os
import time
import requests
from dotenv import load_dotenv

load_dotenv("config/.env")

DURACIONES = {
    "corto": "60-90 segundos",
    "medio": "3-5 minutos",
    "largo": "8-10 minutos"
}

def limpiar_razonamiento(texto):
    """Elimina el razonamiento interno de Kimi y deja solo el script."""
    
    # Indicadores de razonamiento interno
    indicadores_razonamiento = [
        "The user wants", "Looking at", "I need to", "Let me", 
        "First,", "Algorithm", "The garbled", "Given that",
        "I should", "I'll", "I will", "Note:", "Here is",
        "Here's", "This is a", "The following"
    ]
    
    lineas = texto.split("\n")
    script_lineas = []
    en_script = False
    
    for linea in lineas:
        linea_stripped = linea.strip()
        
        # Detectar si es razonamiento
        es_razonamiento = any(linea_stripped.startswith(ind) for ind in indicadores_razonamiento)
        
        # Detectar si es español (tiene tildes o palabras en español)
        tiene_espanol = any(c in linea for c in "áéíóúñÁÉÍÓÚÑ¿¡")
        palabras_espanol = ["el", "la", "los", "las", "en", "de", "que", "un", "una", "fue", "era", "con", "por", "para"]
        tiene_palabras_espanol = any(f" {p} " in linea.lower() for p in palabras_espanol)
        
        if not en_script:
            if (tiene_espanol or tiene_palabras_espanol) and not es_razonamiento:
                en_script = True
                script_lineas.append(linea)
        else:
            # Parar si vuelve al razonamiento
            if es_razonamiento and not tiene_espanol:
                break
            script_lineas.append(linea)
    
    resultado = "\n".join(script_lineas).strip()
    
    # Limpiar markdown
    resultado = resultado.replace("**", "").replace("##", "").replace("# ", "")
    
    return resultado if len(resultado) > 50 else texto

def generar_script(tema, duracion="corto", sistema=None, intentos=3):
    duracion_texto = DURACIONES.get(duracion, "60-90 segundos")
    
    if not sistema:
        sistema = "Eres un narrador apasionado de historias"

    for intento in range(intentos):
        try:
            print(f"  Intento {intento+1}/{intentos}...")
            response = requests.post(
                url="https://integrate.api.nvidia.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('NVIDIA_API_KEY')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "moonshotai/kimi-k2.6",
                    "stream": False,
                    "temperature": 0.7,
                    "messages": [
                        {
                            "role": "system",
                            "content": sistema
                        },
                        {
                            "role": "user",
                            "content": f"Escribe un script de YouTube de {duracion_texto} sobre: {tema}. Solo el texto para narrar en voz alta, sin explicaciones."
                        }
                    ],
                    "max_tokens": 2048
                },
                timeout=300
            )
            if response.status_code != 200:
                print(f"  Error HTTP {response.status_code}: {response.text}")
                if intento < intentos - 1:
                    print(f"  Reintentando en 10 segundos...")
                    time.sleep(10)
                continue
            try:
                data = response.json()
            except ValueError:
                print(f"  Error parseando JSON: {response.text}")
                if intento < intentos - 1:
                    print(f"  Reintentando en 10 segundos...")
                    time.sleep(10)
                continue
            if not data.get("choices") or not data["choices"][0].get("message"):
                print(f"  Respuesta inesperada: {json.dumps(data, ensure_ascii=False)[:1000]}")
                if intento < intentos - 1:
                    print(f"  Reintentando en 10 segundos...")
                    time.sleep(10)
                continue
            texto = data["choices"][0]["message"]["content"]
            
            # Limpiar razonamiento
            texto_limpio = limpiar_razonamiento(texto)
            
            if len(texto_limpio) > 100:
                return texto_limpio
            else:
                print(f"  Script muy corto o en inglés, reintentando...")
                if intento < intentos - 1:
                    time.sleep(10)
                continue
                
        except Exception as e:
            print(f"  Error: {e}")
            if intento < intentos - 1:
                print(f"  Reintentando en 10 segundos...")
                time.sleep(10)
    
    raise Exception("No se pudo generar el script después de 3 intentos")

if __name__ == "__main__":
    tema = input("Tema:\n> ").strip()
    script = generar_script(tema)
    print("\n" + "="*50)
    print(script)
    print("="*50)
