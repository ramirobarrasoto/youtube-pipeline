import os
import asyncio
import edge_tts
from dotenv import load_dotenv

load_dotenv("config/.env")

VOCES = {
    "Carlos":  "es-MX-JorgeNeural",
    "Alvaro":  "es-ES-AlvaroNeural",
    "Andres":  "es-CO-GonzaloNeural",
}

async def generar_audio_async(script: str, voz: str = "Carlos", nombre_archivo: str = "videos_output/audio/narration.mp3") -> str:
    voice = VOCES.get(voz, VOCES["Carlos"])
    os.makedirs(os.path.dirname(nombre_archivo), exist_ok=True)
    communicate = edge_tts.Communicate(script, voice)
    await communicate.save(nombre_archivo)
    return nombre_archivo

def generar_audio(script: str, voz: str = "Carlos", nombre_archivo: str = "videos_output/audio/narration.mp3") -> str:
    print(f"⏳ Generando audio con voz: {voz}...")
    path = asyncio.run(generar_audio_async(script, voz, nombre_archivo))
    print(f"✅ Audio guardado en: {path}")
    return path

if __name__ == "__main__":
    with open("videos_output/script.txt", "r") as f:
        script = f.read()
    generar_audio(script)
