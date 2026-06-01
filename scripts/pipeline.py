import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv("config/.env")

# Verificar credenciales
def verificar_credenciales():
    errores = []
    
    if not os.getenv("ANTHROPIC_API_KEY"):
        errores.append("❌ ANTHROPIC_API_KEY no encontrada")
    else:
        print("✅ Anthropic API Key cargada")
        
    if not os.getenv("ELEVENLABS_API_KEY"):
        errores.append("❌ ELEVENLABS_API_KEY no encontrada")
    else:
        print("✅ ElevenLabs API Key cargada")
        
    credentials_path = os.getenv("YOUTUBE_CREDENTIALS")
    if not credentials_path or not Path(credentials_path).exists():
        errores.append("❌ YouTube credentials.json no encontrado")
    else:
        print("✅ YouTube credentials.json encontrado")
    
    if errores:
        print("\n⚠️ Errores encontrados:")
        for e in errores:
            print(e)
        sys.exit(1)
    else:
        print("\n🎉 Todo listo para empezar!")

if __name__ == "__main__":
    print("🔍 Verificando credenciales...\n")
    verificar_credenciales()
