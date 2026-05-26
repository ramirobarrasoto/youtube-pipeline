import os
import time
import requests
from urllib.parse import quote
from PIL import Image
from io import BytesIO

def generar_imagen_con_reintento(prompt: str, output_path: str, intentos: int = 3) -> bool:
    url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=1080&height=1920&nologo=true&seed={int(time.time())}"
    for intento in range(intentos):
        try:
            response = requests.get(url, timeout=90)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content)).convert("RGB")
                img.save(output_path, "JPEG", quality=90)
                return True
            else:
                print(f"  ⚠️ Intento {intento+1}: Error {response.status_code}")
                time.sleep(5)
        except Exception as e:
            print(f"  ⚠️ Intento {intento+1}: {e}")
            time.sleep(5)
    return False

def generar_imagenes(tema: str, output_dir: str = "videos_output/images", cantidad: int = 4, estilo: str = "cinematic, dramatic, historical"):
    os.makedirs(output_dir, exist_ok=True)
    
    prompts = [
        f"{tema}, {estilo}, epic moment",
        f"{tema}, {estilo}, wide angle shot",
        f"{tema}, {estilo}, close up dramatic",
        f"{tema}, {estilo}, emotional atmosphere",
        f"{tema}, {estilo}, action scene",
        f"{tema}, {estilo}, historical context",
        f"{tema}, {estilo}, crowd reaction",
        f"{tema}, {estilo}, iconic moment",
    ]
    
    imagenes = []
    for i, prompt in enumerate(prompts[:cantidad]):
        print(f"  🖼️ Generando imagen {i+1}/{cantidad}...")
        output_path = f"{output_dir}/img{i+1}.jpg"
        if generar_imagen_con_reintento(prompt, output_path):
            imagenes.append(output_path)
            print(f"  ✅ Imagen {i+1} guardada")
        else:
            print(f"  ⚠️ Imagen {i+1} falló, continuando...")
    
    if not imagenes:
        print("  ⚠️ Usando imagen de fallback...")
        img = Image.new("RGB", (1080, 1920), color=(20, 20, 20))
        fallback_path = f"{output_dir}/img1.jpg"
        img.save(fallback_path)
        imagenes.append(fallback_path)
    
    print(f"  ✅ {len(imagenes)} imágenes listas")
    return imagenes

if __name__ == "__main__":
    generar_imagenes("Uruguay 1930 World Cup final")
