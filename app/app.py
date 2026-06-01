import sys
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.ERROR, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler()])
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(BASE_DIR, "scripts"))

from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from PIL import Image as PILImage
import threading
import json
import time

load_dotenv(os.path.join(BASE_DIR, "config/.env"))
app = Flask(__name__)

pipeline_status = {"running": False, "steps": [], "error": None, "video_url": None, "checkpoint": None, "checkpoint_data": {}}
checkpoint_event = threading.Event()
checkpoint_aprobado = {"value": True}
script_editado = {"value": None}
script_editado_multi = {"value": {}}

def log_step(mensaje, estado="active"):
    existing = [s for s in pipeline_status["steps"] if s["mensaje"] == mensaje]
    if existing:
        existing[0]["estado"] = estado
    else:
        pipeline_status["steps"].append({"mensaje": mensaje, "estado": estado})

def esperar_checkpoint(tipo, data={}):
    pipeline_status["checkpoint"] = tipo
    pipeline_status["checkpoint_data"] = data
    pipeline_status["running"] = False
    checkpoint_event.clear()
    checkpoint_event.wait()
    pipeline_status["checkpoint"] = None
    pipeline_status["checkpoint_data"] = {}
    pipeline_status["running"] = True
    return checkpoint_aprobado["value"]

def run_pipeline(canal, tema, duracion, voz, privacidad, cantidad_imagenes, genero_musica="sin_musica"):
    global pipeline_status
    pipeline_status = {"running": True, "steps": [], "error": None, "video_url": None, "checkpoint": None, "checkpoint_data": {}}
    plan_produccion = None
    try:
        os.chdir(BASE_DIR)
        with open(f"perfiles/{canal}.json") as f:
            perfil = json.load(f)
        env_file = perfil.get("env_file", "config/.env")
        env_path = os.path.join(BASE_DIR, env_file)
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)
        nombre_carpeta = tema[:30].replace(" ", "_").replace("/", "-")
        base_dir = f"videos_output/{canal}/{nombre_carpeta}"
        os.makedirs(f"{base_dir}/images", exist_ok=True)

        # ── Director IA ───────────────────────────────────────────────────
        log_step("Consultando Director IA...")
        from director import generar_plan, plan_a_script, plan_a_queries
        estilo = perfil.get("estilo_imagenes", "cinematic, dramatic")
        plan_produccion = generar_plan(
            tema=tema,
            duracion=duracion,
            estilo=estilo,
            sistema=perfil.get("prompt_sistema"),
        )
        script = plan_a_script(plan_produccion)
        with open(f"{base_dir}/plan.json", "w") as f:
            json.dump(plan_produccion, f, ensure_ascii=False, indent=2)
        with open(f"{base_dir}/script.txt", "w") as f:
            f.write(script)
        log_step("Plan de produccion generado", "done")

        script_editado["value"] = script
        log_step("Esperando revision del script...", "checkpoint")
        esperar_checkpoint("script", {"script": script, "plan": plan_produccion})
        script = script_editado["value"]
        with open(f"{base_dir}/script.txt", "w") as f:
            f.write(script)
        log_step("Script aprobado", "done")

        log_step("Generando audio...")
        from generar_audio import generar_audio
        audio_path = os.path.join(BASE_DIR, f"{base_dir}/narration.mp3")
        generar_audio(script=script, voz=voz, nombre_archivo=audio_path)
        log_step("Audio generado", "done")

        log_step("Esperando aprobacion del audio...", "checkpoint")
        aprobado = esperar_checkpoint("audio", {"audio_path": audio_path, "script": script})
        if not aprobado:
            log_step("Regenerando audio...", "active")
            generar_audio(script=script, voz=voz, nombre_archivo=audio_path)
            log_step("Audio regenerado", "done")
            esperar_checkpoint("audio", {"audio_path": audio_path, "script": script})
        log_step("Audio aprobado", "done")

        # Reescalar timings del plan a la duración real del audio
        try:
            from moviepy.editor import AudioFileClip as _AFC
            from director import reescalar_timings
            _audio_tmp = _AFC(audio_path)
            duracion_real = _audio_tmp.duration
            _audio_tmp.close()
            plan_produccion = reescalar_timings(plan_produccion, duracion_real)
            with open(f"{base_dir}/plan.json", "w") as f:
                json.dump(plan_produccion, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"No se pudo reescalar timings: {e}")

        log_step("Generando imagenes...")
        from generar_imagenes import generar_imagenes
        images_dir = os.path.join(BASE_DIR, f"{base_dir}/images")
        queries = plan_a_queries(plan_produccion)[:int(cantidad_imagenes)]
        generar_imagenes(
            tema,
            output_dir=images_dir,
            cantidad=int(cantidad_imagenes),
            estilo=estilo,
            queries=queries if queries else None,
        )
        log_step("Imagenes generadas", "done")

        imagenes = sorted(
            [os.path.join(images_dir, f) for f in os.listdir(images_dir)
             if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))],
            key=lambda p: os.path.basename(p)
        )
        log_step("Esperando aprobacion de imagenes...", "checkpoint")
        aprobado = esperar_checkpoint("imagenes", {"imagenes": imagenes})
        if not aprobado:
            log_step("Regenerando imagenes...", "active")
            generar_imagenes(
                tema,
                output_dir=images_dir,
                cantidad=int(cantidad_imagenes),
                estilo=estilo,
                queries=queries if queries else None,
            )
            log_step("Imagenes regeneradas", "done")
            imagenes = sorted(
                [os.path.join(images_dir, f) for f in os.listdir(images_dir)
                 if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))],
                key=lambda p: os.path.basename(p)
            )
            esperar_checkpoint("imagenes", {"imagenes": imagenes})
        log_step("Imagenes aprobadas", "done")

        musica_label = genero_musica if genero_musica and genero_musica != "sin_musica" else "sin música"
        log_step(f"Compilando video con Ken Burns, subtitulos y {musica_label}...")
        from pipeline_video import pipeline_video_completo
        video_path = pipeline_video_completo(
            audio_path=audio_path,
            images_dir=images_dir,
            output_dir=os.path.join(BASE_DIR, base_dir),
            con_subtitulos=True,
            genero_musica=genero_musica,
            plan_produccion=plan_produccion,
        )
        log_step("Video compilado", "done")

        log_step("Generando thumbnail...")
        from generar_thumbnail import generar_thumbnail
        thumbnail_path = os.path.join(BASE_DIR, f"{base_dir}/thumbnail.jpg")
        generar_thumbnail(tema=tema, output_path=thumbnail_path)
        log_step("Thumbnail generado", "done")

        log_step("Subiendo a YouTube...")
        from subir_youtube import subir_video
        descripcion = f"{script[:300]}...\n\nSuscribete a {perfil[chr(39)+'nombre'+chr(39)]} para mas contenido."
        url = subir_video(video_path=video_path, titulo=tema, descripcion=descripcion, thumbnail_path=thumbnail_path, privacidad=privacidad)
        log_step("Video subido a YouTube", "done")
        pipeline_status["video_url"] = url

        video_id = url.split("v=")[-1] if "v=" in url else ""
        metadata = {"tema": tema, "canal": canal, "canal_nombre": perfil.get("nombre", canal),
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "duracion": duracion, "voz": voz,
            "youtube_url": url, "youtube_id": video_id, "privacidad": privacidad}
        with open(os.path.join(BASE_DIR, f"{base_dir}/metadata.json"), "w") as mf:
            json.dump(metadata, mf, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        pipeline_status["error"] = str(e)
        log_step(f"Error: {str(e)}", "error")
    finally:
        pipeline_status["running"] = False
        pipeline_status["checkpoint"] = None


def run_pipeline_multiidioma(canal_base, tema, duracion, privacidad, cantidad_imagenes, genero_musica="sin_musica"):
    """Genera el mismo video en ES, EN y PT con checkpoints multi-idioma."""
    global pipeline_status
    pipeline_status = {"running": True, "steps": [], "error": None, "video_url": None, "checkpoint": None, "checkpoint_data": {}}
    
    idiomas = ["es", "en", "pt"]
    perfiles = {}
    scripts = {}
    audios = {}
    
    try:
        os.chdir(BASE_DIR)
        
        # Cargar perfiles
        for idioma in idiomas:
            perfil_key = f"{canal_base}_{idioma}"
            with open(f"perfiles/{perfil_key}.json") as f:
                perfiles[idioma] = json.load(f)
        
        nombre_carpeta = tema[:30].replace(" ", "_").replace("/", "-")
        base_dir = f"videos_output/{canal_base}/{nombre_carpeta}"
        os.makedirs(f"{base_dir}/images", exist_ok=True)
        
        # PASO 1: Generar los 3 scripts via Director IA
        log_step("Consultando Director IA para ES, EN y PT...")
        from director import generar_plan, plan_a_script, plan_a_queries, reescalar_timings
        planes = {}
        for idioma in idiomas:
            perfil = perfiles[idioma]
            log_step(f"Director IA [{idioma.upper()}]...")
            estilo = perfil.get("estilo_imagenes", "cinematic, dramatic")
            plan = generar_plan(
                tema=tema,
                duracion=duracion,
                estilo=estilo,
                sistema=perfil.get("prompt_sistema"),
            )
            planes[idioma] = plan
            script = plan_a_script(plan)
            scripts[idioma] = script
            os.makedirs(f"{base_dir}/{idioma}", exist_ok=True)
            with open(f"{base_dir}/{idioma}/plan.json", "w") as f:
                json.dump(plan, f, ensure_ascii=False, indent=2)
            with open(f"{base_dir}/{idioma}/script.txt", "w") as f:
                f.write(script)
            log_step(f"Plan [{idioma.upper()}] generado", "done")
        
        # CHECKPOINT 1: Revisar los 3 scripts con tabs
        script_editado_multi["value"] = dict(scripts)
        log_step("Esperando revision de scripts...", "checkpoint")
        esperar_checkpoint("scripts_multi", {
            "scripts": scripts,
            "idiomas": idiomas,
            "planes": {k: v for k, v in planes.items()},
        })
        scripts = dict(script_editado_multi["value"])
        for idioma in idiomas:
            with open(f"{base_dir}/{idioma}/script.txt", "w") as f:
                f.write(scripts[idioma])
        log_step("Scripts aprobados", "done")
        
        # PASO 2: Generar los 3 audios
        from generar_audio import generar_audio
        for idioma in idiomas:
            perfil = perfiles[idioma]
            voz = perfil.get("voz_default", "es-MX-JorgeNeural")
            audio_path = os.path.join(BASE_DIR, f"{base_dir}/{idioma}/narration.mp3")
            log_step(f"Generando audio [{idioma.upper()}]...")
            generar_audio(script=scripts[idioma], voz=voz, nombre_archivo=audio_path)
            audios[idioma] = audio_path
            log_step(f"Audio [{idioma.upper()}] generado", "done")
        
        # CHECKPOINT 2: Revisar los 3 audios con tabs
        log_step("Esperando aprobacion de audios...", "checkpoint")
        esperar_checkpoint("audios_multi", {
            "audios": audios,
            "scripts": scripts,
            "idiomas": idiomas
        })
        log_step("Audios aprobados", "done")
        
        # Reescalar timings de cada plan al audio real generado
        from moviepy.editor import AudioFileClip as _AFC
        for idioma in idiomas:
            try:
                _a = _AFC(audios[idioma])
                dur_real = _a.duration
                _a.close()
                planes[idioma] = reescalar_timings(planes[idioma], dur_real)
                with open(f"{base_dir}/{idioma}/plan.json", "w") as f:
                    json.dump(planes[idioma], f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"No se pudo reescalar timings [{idioma}]: {e}")

        # PASO 3: Imágenes (compartidas, usando queries del plan ES)
        log_step("Generando imagenes...")
        from generar_imagenes import generar_imagenes
        images_dir = os.path.join(BASE_DIR, f"{base_dir}/images")
        estilo = perfiles["es"].get("estilo_imagenes", "cinematic, dramatic")
        queries_es = plan_a_queries(planes["es"])[:int(cantidad_imagenes)]
        generar_imagenes(
            tema,
            output_dir=images_dir,
            cantidad=int(cantidad_imagenes),
            estilo=estilo,
            queries=queries_es if queries_es else None,
        )
        log_step("Imagenes generadas", "done")

        # CHECKPOINT 3: Revisar imágenes
        imagenes = sorted(
            [os.path.join(images_dir, f) for f in os.listdir(images_dir)
             if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))],
            key=lambda p: os.path.basename(p)
        )
        log_step("Esperando aprobacion de imagenes...", "checkpoint")
        aprobado = esperar_checkpoint("imagenes", {"imagenes": imagenes})
        if not aprobado:
            log_step("Regenerando imagenes...", "active")
            generar_imagenes(
                tema,
                output_dir=images_dir,
                cantidad=int(cantidad_imagenes),
                estilo=estilo,
                queries=queries_es if queries_es else None,
            )
            log_step("Imagenes regeneradas", "done")
            imagenes = sorted(
                [os.path.join(images_dir, f) for f in os.listdir(images_dir)
                 if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))],
                key=lambda p: os.path.basename(p)
            )
            esperar_checkpoint("imagenes", {"imagenes": imagenes})
        log_step("Imagenes aprobadas", "done")
        
        # PASO 4: Compilar 3 videos y subir
        from pipeline_video import pipeline_video_completo
        from generar_thumbnail import generar_thumbnail
        from subir_youtube import subir_video
        
        thumbnail_path = os.path.join(BASE_DIR, f"{base_dir}/thumbnail.jpg")
        generar_thumbnail(tema=tema, output_path=thumbnail_path)
        
        urls = {}
        for idioma in idiomas:
            perfil = perfiles[idioma]
            log_step(f"Compilando video [{idioma.upper()}]...")
            video_path = pipeline_video_completo(
                audio_path=audios[idioma],
                images_dir=images_dir,
                output_dir=os.path.join(BASE_DIR, f"{base_dir}/{idioma}"),
                con_subtitulos=True,
                genero_musica=genero_musica,
                plan_produccion=planes.get(idioma),
            )
            log_step(f"Video [{idioma.upper()}] compilado", "done")
            
            log_step(f"Subiendo video [{idioma.upper()}] a YouTube...")
            descripcion = f"{scripts[idioma][:300]}...\n\nSuscribete a {perfil[chr(39)+'nombre'+chr(39)]}."
            url = subir_video(
                video_path=video_path,
                titulo=tema,
                descripcion=descripcion,
                thumbnail_path=thumbnail_path,
                privacidad=privacidad
            )
            urls[idioma] = url
            log_step(f"Video [{idioma.upper()}] subido", "done")
            
            # Guardar metadata
            metadata = {
                "tema": tema, "canal": f"{canal_base}_{idioma}",
                "canal_nombre": perfil.get("nombre", canal_base),
                "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "duracion": duracion, "idioma": idioma,
                "youtube_url": url, "privacidad": privacidad
            }
            with open(os.path.join(BASE_DIR, f"{base_dir}/{idioma}/metadata.json"), "w") as mf:
                json.dump(metadata, mf, ensure_ascii=False, indent=2)
        
        pipeline_status["video_url"] = urls.get("es", list(urls.values())[0])
        pipeline_status["video_urls_multi"] = urls
        
    except Exception as e:
        logger.error(f"Error multiidioma: {str(e)}", exc_info=True)
        pipeline_status["error"] = str(e)
        log_step(f"Error: {str(e)}", "error")
    finally:
        pipeline_status["running"] = False
        pipeline_status["checkpoint"] = None


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generar", methods=["POST"])
def generar():
    if pipeline_status["running"] or pipeline_status["checkpoint"]:
        return jsonify({"error": "Pipeline ya esta corriendo"}), 400
    data = request.json
    thread = threading.Thread(target=run_pipeline, kwargs={"canal": data["canal"], "tema": data["tema"],
        "duracion": data["duracion"], "voz": data["voz"], "privacidad": data["privacidad"],
        "cantidad_imagenes": data["imagenes"], "genero_musica": data.get("musica", "sin_musica")})
    thread.daemon = True
    thread.start()
    return jsonify({"ok": True})


@app.route("/generar_todos", methods=["POST"])
def generar_todos():
    if pipeline_status["running"] or pipeline_status["checkpoint"]:
        return jsonify({"error": "Pipeline ya esta corriendo"}), 400
    data = request.json
    canal_base = data["canal_base"]  # ej: "futbol", "cuentos", "biografias"
    thread = threading.Thread(target=run_pipeline_multiidioma, kwargs={
        "canal_base": canal_base,
        "tema": data["tema"],
        "duracion": data["duracion"],
        "privacidad": data["privacidad"],
        "cantidad_imagenes": data["imagenes"],
        "genero_musica": data.get("musica", "sin_musica"),
    })
    thread.daemon = True
    thread.start()
    return jsonify({"ok": True})


@app.route("/aprobar_multi", methods=["POST"])
def aprobar_multi():
    data = request.json or {}
    if "scripts" in data:
        script_editado_multi["value"] = data["scripts"]
    checkpoint_aprobado["value"] = True
    checkpoint_event.set()
    return jsonify({"ok": True})

@app.route("/audio_multi/<idioma>")
def serve_audio_multi(idioma):
    data = pipeline_status.get("checkpoint_data", {})
    audios = data.get("audios", {})
    audio_path = audios.get(idioma)
    if audio_path and os.path.exists(audio_path):
        return send_file(audio_path, mimetype="audio/mpeg", conditional=True)
    return "No audio", 404

@app.route("/aprobar", methods=["POST"])
def aprobar():
    data = request.json or {}
    if "script" in data:
        script_editado["value"] = data["script"]
    checkpoint_aprobado["value"] = True
    checkpoint_event.set()
    return jsonify({"ok": True})

@app.route("/rechazar", methods=["POST"])
def rechazar():
    checkpoint_aprobado["value"] = False
    pipeline_status["running"] = True
    checkpoint_event.set()
    return jsonify({"ok": True})

@app.route("/status")
def status():
    return jsonify(pipeline_status)

@app.route("/audio")
def serve_audio():
    data = pipeline_status.get("checkpoint_data", {})
    audio_path = data.get("audio_path")
    if audio_path and os.path.exists(audio_path):
        return send_file(audio_path, mimetype="audio/mpeg", conditional=True)
    return "No audio", 404

@app.route("/imagen/<int:idx>")
def serve_imagen(idx):
    data = pipeline_status.get("checkpoint_data", {})
    imagenes = data.get("imagenes", [])
    if idx < len(imagenes) and os.path.exists(imagenes[idx]):
        return send_file(imagenes[idx], mimetype="image/jpeg")
    return "No imagen", 404

@app.route("/eliminar_imagen/<int:idx>", methods=["POST"])
def eliminar_imagen(idx):
    data = pipeline_status.get("checkpoint_data", {})
    imagenes = data.get("imagenes", [])
    if 0 <= idx < len(imagenes):
        path = imagenes[idx]
        if os.path.exists(path):
            os.remove(path)
        imagenes.pop(idx)
        pipeline_status["checkpoint_data"]["imagenes"] = imagenes
    return jsonify({"ok": True, "imagenes_count": len(imagenes)})

@app.route("/subir_imagenes", methods=["POST"])
def subir_imagenes():
    data = pipeline_status.get("checkpoint_data", {})
    imagenes = data.get("imagenes", [])
    files = request.files.getlist("files")
    info_msgs = []
    if not files:
        return jsonify({"error": "No se recibieron archivos"}), 400
    img_dir = os.path.dirname(imagenes[0]) if imagenes else os.path.join(BASE_DIR, "videos_output", "uploads")
    os.makedirs(img_dir, exist_ok=True)
    for file in files:
        try:
            img = PILImage.open(file.stream).convert("RGB")
            w, h = img.size
            if w != 1080 or h != 1920:
                info_msgs.append(f"{file.filename}: {w}x{h} redimensionada a 1080x1920")
                img = img.resize((1080, 1920), PILImage.LANCZOS)
            else:
                info_msgs.append(f"{file.filename}: {w}x{h} OK")
            out_path = os.path.join(img_dir, f"custom_{int(time.time()*1000)}.jpg")
            img.save(out_path, "JPEG", quality=90)
            imagenes.append(out_path)
        except Exception as e:
            info_msgs.append(f"{file.filename}: Error - {str(e)}")
    pipeline_status["checkpoint_data"]["imagenes"] = imagenes
    return jsonify({"ok": True, "info": " | ".join(info_msgs), "total": len(imagenes)})

@app.route("/biblioteca")
def biblioteca():
    canal_filtro = request.args.get("canal", "todos")
    canales = ["futbol", "cuentos", "biografias"]
    videos = []
    for canal_dir in canales:
        if canal_filtro != "todos" and canal_filtro != canal_dir:
            continue
        canal_path = os.path.join(BASE_DIR, "videos_output", canal_dir)
        if not os.path.exists(canal_path):
            continue
        for video_dir in sorted(os.listdir(canal_path), reverse=True):
            metadata_path = os.path.join(canal_path, video_dir, "metadata.json")
            if os.path.exists(metadata_path):
                with open(metadata_path) as f:
                    meta = json.load(f)
                meta["carpeta"] = f"{canal_dir}/{video_dir}"
                meta["tiene_script"] = os.path.exists(os.path.join(canal_path, video_dir, "script.txt"))
                meta["tiene_thumbnail"] = os.path.exists(os.path.join(canal_path, video_dir, "thumbnail.jpg"))
                images_path = os.path.join(canal_path, video_dir, "images")
                meta["cantidad_imagenes"] = len([f for f in os.listdir(images_path) if f.endswith((".jpg",".png",".webp"))]) if os.path.exists(images_path) else 0
                videos.append(meta)
    return jsonify(videos)

@app.route("/plan")
def get_plan():
    """Devuelve el plan de producción del checkpoint actual."""
    data = pipeline_status.get("checkpoint_data", {})
    plan = data.get("plan")
    if plan:
        return jsonify(plan)
    return jsonify({"error": "No hay plan de producción disponible"}), 404

@app.route("/biblioteca/script/<path:carpeta>")
def get_script(carpeta):
    script_path = os.path.join(BASE_DIR, "videos_output", carpeta, "script.txt")
    if os.path.exists(script_path):
        with open(script_path) as f:
            return jsonify({"script": f.read()})
    return jsonify({"error": "No encontrado"}), 404

@app.route("/biblioteca/thumbnail/<path:carpeta>")
def get_thumbnail(carpeta):
    thumb_path = os.path.join(BASE_DIR, "videos_output", carpeta, "thumbnail.jpg")
    if os.path.exists(thumb_path):
        return send_file(thumb_path, mimetype="image/jpeg")
    return "No thumbnail", 404

# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE EXPERIMENTAL V2 — Gemini + FFmpeg (aislado, no toca el pipeline actual)
# ─────────────────────────────────────────────────────────────────────────────

pipeline_status_v2 = {
    "running": False, "steps": [], "error": None,
    "video_path": None, "escenas_total": 0,
}


def log_step_v2(mensaje, estado="active"):
    existing = [s for s in pipeline_status_v2["steps"] if s["mensaje"] == mensaje]
    if existing:
        existing[0]["estado"] = estado
    else:
        pipeline_status_v2["steps"].append({"mensaje": mensaje, "estado": estado})


def run_pipeline_v2(canal, tema, duracion, voz, privacidad, genero_musica, idioma, estilo_imagenes):
    global pipeline_status_v2
    pipeline_status_v2 = {
        "running": True, "steps": [], "error": None,
        "video_path": None, "escenas_total": 0,
    }
    try:
        os.chdir(BASE_DIR)
        sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))

        from pipeline_experimental import pipeline_experimental
        video_path = pipeline_experimental(
            canal=canal,
            tema=tema,
            duracion=duracion,
            voz=voz,
            idioma=idioma,
            privacidad=privacidad,
            genero_musica=genero_musica,
            estilo_imagenes=estilo_imagenes,
            output_base=os.path.join(BASE_DIR, "videos_output"),
            log_fn=log_step_v2,
        )
        pipeline_status_v2["video_path"] = video_path
    except Exception as e:
        logger.error(f"Error pipeline V2: {str(e)}", exc_info=True)
        pipeline_status_v2["error"] = str(e)
        log_step_v2(f"Error: {str(e)}", "error")
    finally:
        pipeline_status_v2["running"] = False


@app.route("/api/v2/generar", methods=["POST"])
def generar_v2():
    """Endpoint experimental V2 — Gemini + FFmpeg para videos largos."""
    if pipeline_status_v2["running"]:
        return jsonify({"error": "Pipeline V2 ya está corriendo"}), 400
    data = request.json or {}
    required = ["canal", "tema", "duracion", "voz"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Campo requerido: {field}"}), 400

    thread = threading.Thread(
        target=run_pipeline_v2,
        kwargs={
            "canal":           data["canal"],
            "tema":            data["tema"],
            "duracion":        data["duracion"],
            "voz":             data.get("voz", "es-MX-JorgeNeural"),
            "privacidad":      data.get("privacidad", "private"),
            "genero_musica":   data.get("musica", "sin_musica"),
            "idioma":          data.get("idioma", "español"),
            "estilo_imagenes": data.get("estilo_imagenes", "cinematic 4K dramatic"),
        },
    )
    thread.daemon = True
    thread.start()
    return jsonify({"ok": True, "mensaje": "Pipeline experimental V2 iniciado"})


@app.route("/api/v2/status")
def status_v2():
    """Estado del pipeline experimental V2."""
    return jsonify(pipeline_status_v2)


@app.route("/api/v2/modelos")
def modelos_gemini():
    """Lista los modelos Gemini disponibles con la API key configurada."""
    try:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            return jsonify({"error": "GEMINI_API_KEY no configurada"}), 400
        client = genai.Client(api_key=api_key)
        modelos = [m.name for m in client.models.list()]
        modelos_flash = [m for m in modelos if "flash" in m.lower() or "pro" in m.lower()]
        return jsonify({"modelos": modelos_flash, "modelo_actual": os.getenv("GEMINI_MODEL", "gemini-2.5-flash")})
    except ImportError:
        return jsonify({"error": "SDK no instalado: pip install google-genai"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=False, port=5000)
