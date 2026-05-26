import os
import time
import requests
from urllib.parse import quote
from PIL import Image
from io import BytesIO

def generar_thumbnail(tema: str, output_path: str = "videos_output/thumbnail.jpg") -> str:
    prompt = f"YouTube thumbnail: {tema}, dramatic, high contrast, vintage soccer, bold colors, cinematic, emotional, viral style"
    
    print(f"⏳ Generando thumbnail...")
    
    url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=1280&height=720&nologo=true&seed={int(time.time())}"
    
    for intento in range(3):
        try:
            response = requests.get(url, timeout=90)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
                img.save(output_path, "JPEG", quality=95)
                print(f"✅ Thumbnail guardado en: {output_path}")
                return output_path
            else:
                print(f"⚠️ Intento {intento+1}: Error {response.status_code}, reintentando...")
                time.sleep(5)
        except Exception as e:
            print(f"⚠️ Intento {intento+1}: {e}, reintentando...")
            time.sleep(5)
    
    print("⚠️ Thumbnail falló, continuando sin thumbnail...")
    return None
