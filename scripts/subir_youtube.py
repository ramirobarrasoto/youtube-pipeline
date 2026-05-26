import os
import pickle
from pathlib import Path
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

load_dotenv("config/.env")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CREDENTIALS_FILE = os.getenv("YOUTUBE_CREDENTIALS")
TOKEN_FILE = "config/token.pickle"

def autenticar():
    creds = None
    if Path(TOKEN_FILE).exists():
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    return build("youtube", "v3", credentials=creds)

def subir_video(video_path, titulo, descripcion, thumbnail_path=None, privacidad="private"):
    print("🔐 Autenticando con YouTube...")
    youtube = autenticar()
    
    print(f"⏳ Subiendo video: {titulo}")
    body = {
        "snippet": {
            "title": titulo,
            "description": descripcion,
            "tags": ["fútbol", "historia", "mundiales", "2026"],
            "categoryId": "17"
        },
        "status": {"privacyStatus": privacidad}
    }
    
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    video_id = response["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    if thumbnail_path and Path(thumbnail_path).exists():
        try:
            print("⏳ Subiendo thumbnail...")
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path)
            ).execute()
            print("✅ Thumbnail subido")
        except Exception:
            print("⚠️  Thumbnail omitido (verificá el canal en YouTube Studio para habilitarlo)")
    
    print(f"\n✅ Video subido!")
    print(f"🔗 {video_url}")
    print(f"👁️  Estado: PRIVADO")
    return video_url

if __name__ == "__main__":
    subir_video(
        video_path="videos_output/final/video_final.mp4",
        titulo="El Primer Mundial de Fútbol - Uruguay 1930",
        descripcion="Test",
        privacidad="private"
    )
