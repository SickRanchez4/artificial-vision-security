import logging
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from flask import Blueprint, Response, current_app, jsonify, request

from backend.streaming.session_repository import close_session, create_session, mark_session_error
from backend.streaming.sources.factory import create_video_source

logger = logging.getLogger(__name__)

streaming_bp = Blueprint("streaming", __name__)

# RF-2.2: extensión y tamaño máximo aceptados para el archivo subido.
ALLOWED_UPLOAD_EXTENSION = ".mp4"
MAX_UPLOAD_SIZE_BYTES = 256 * 1024 * 1024
INVALID_FILE_ERROR = "Archivo no válido o mayor a 256 MB."
CAMERA_SESSION_ERROR = "No hay una sesión de cámara activa."


@streaming_bp.get("/api/stream")
def stream():
	pipeline = current_app.extensions["detection_pipeline"]

	def generate_frames():
		while True:
			frame, _ = pipeline.wait_for_frame()
			yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"

	status = "online" if pipeline.source_online else "offline"
	return Response(
		generate_frames(),
		mimetype="multipart/x-mixed-replace; boundary=frame",
		headers={"X-Source-Status": status, "Cache-Control": "no-store"},
	)


@streaming_bp.get("/api/streaming/source/status")
def source_status():
	status = current_app.extensions.get("video_source_status", {"status": "idle", "error_message": None})
	return jsonify(**status)


@streaming_bp.post("/api/streaming/source")
def create_source():
	uploaded = request.files.get("file")
	if uploaded is not None:
		return _create_file_source(uploaded)

	payload = request.get_json(silent=True) or {}
	if payload.get("type") == "live":
		return _create_camera_source()

	return jsonify(error="Tipo de fuente no soportado."), 400


@streaming_bp.post("/api/streaming/camera-frame")
def push_camera_frame():
	camera_source = current_app.extensions.get("camera_source")
	if camera_source is None or not camera_source.is_active:
		return jsonify(error=CAMERA_SESSION_ERROR), 409

	frame = cv2.imdecode(np.frombuffer(request.get_data(), dtype=np.uint8), cv2.IMREAD_COLOR)
	if frame is None:
		return jsonify(error="Frame de cámara no válido."), 400

	if not camera_source.push_frame(frame):
		return jsonify(error=CAMERA_SESSION_ERROR), 409

	return "", 204


@streaming_bp.post("/api/streaming/source/error")
def report_source_error():
	"""Recibe errores detectados en el navegador (RF-3.4): cámara perdida.

	Sin reintento automático: solo se marca la sesión activa como `error`
	con el mensaje recibido y se libera el recurso en el backend.
	"""
	payload = request.get_json(silent=True) or {}
	message = str(payload.get("message") or "Se perdió la conexión con la fuente de video.")
	_stop_active_video(status="error", error_message=message)
	return jsonify(ok=True)


@streaming_bp.delete("/api/streaming/source")
def delete_source():
	_stop_active_video(status="finished")
	return jsonify(ok=True)


def _create_camera_source() -> tuple:
	_stop_active_video(status="finished")

	pipeline = current_app.extensions["detection_pipeline"]
	session_id = uuid4()

	camera_source = create_video_source("live")
	pipeline.set_active_source(camera_source)
	current_app.extensions["camera_source"] = camera_source
	current_app.extensions["active_video_session_id"] = str(session_id)
	current_app.extensions["video_source_status"] = {"status": "connected", "error_message": None}

	create_session(session_id, "live")
	logger.info("Sesión de video %s (cámara) iniciada.", session_id)
	return jsonify(session_id=str(session_id), status="connected"), 202


def _create_file_source(uploaded) -> tuple:
	if not uploaded.filename or not uploaded.filename.lower().endswith(ALLOWED_UPLOAD_EXTENSION):
		return jsonify(error=INVALID_FILE_ERROR), 400

	_stop_active_video(status="finished")

	tmp_dir = Path(current_app.config["VIDEO_UPLOAD_TMP_DIR"])
	tmp_dir.mkdir(parents=True, exist_ok=True)
	session_id = uuid4()
	tmp_path = tmp_dir / f"{session_id}.mp4"

	if not _save_upload_within_limit(uploaded, tmp_path):
		tmp_path.unlink(missing_ok=True)
		return jsonify(error=INVALID_FILE_ERROR), 400

	pipeline = current_app.extensions["detection_pipeline"]
	app = current_app._get_current_object()
	original_name = uploaded.filename

	def _on_end() -> None:
		with app.app_context():
			_stop_active_video(status="finished", expected_session_id=str(session_id))
			logger.info("Sesión de video %s (archivo) finalizada.", session_id)

	def _on_error(message: str) -> None:
		with app.app_context():
			_stop_active_video(status="error", error_message=message, expected_session_id=str(session_id))

	try:
		source = create_video_source("upload", file_path=str(tmp_path))
		source.on_end(_on_end)
		source.on_error(_on_error)
		pipeline.set_active_source(source)
	except Exception:
		tmp_path.unlink(missing_ok=True)
		logger.exception("No se pudo iniciar la fuente de video (archivo).")
		return jsonify(error=INVALID_FILE_ERROR), 400

	current_app.extensions["camera_source"] = None
	current_app.extensions["active_video_session_id"] = str(session_id)
	current_app.extensions["upload_cleanup"] = lambda: tmp_path.unlink(missing_ok=True)
	current_app.extensions["video_source_status"] = {"status": "connected", "error_message": None}
	create_session(session_id, "upload", original_name)
	logger.info("Sesión de video %s (archivo=%s) iniciada.", session_id, original_name)
	return jsonify(session_id=str(session_id)), 202


def _stop_active_video(status: str, error_message: str | None = None, expected_session_id: str | None = None) -> None:
	"""Libera la fuente activa (archivo o cámara) y cierra su sesión (RF-5, RF-6).

	`expected_session_id` evita que un callback tardío de una fuente ya
	reemplazada (por ejemplo, un `_on_end` que dispara después de que el
	usuario ya cambió de fuente) cierre por error la sesión nueva.
	"""
	session_id = current_app.extensions.get("active_video_session_id")
	if expected_session_id is not None and session_id != expected_session_id:
		return

	pipeline = current_app.extensions["detection_pipeline"]
	pipeline.stop_active_source()
	current_app.extensions["camera_source"] = None

	cleanup = current_app.extensions.pop("upload_cleanup", None)
	if cleanup is not None:
		cleanup()

	current_app.extensions["active_video_session_id"] = None
	if session_id:
		if status == "error":
			mark_session_error(session_id, error_message or "Error desconocido.")
		else:
			close_session(session_id)
		logger.info("Sesión de video %s finalizada (%s).", session_id, status)

	current_app.extensions["video_source_status"] = {
		"status": status if status == "error" else "idle",
		"error_message": error_message,
	}


def _save_upload_within_limit(uploaded, destination: Path) -> bool:
	size = 0
	with destination.open("wb") as handle:
		while True:
			chunk = uploaded.stream.read(1024 * 1024)
			if not chunk:
				break
			size += len(chunk)
			if size > MAX_UPLOAD_SIZE_BYTES:
				return False
			handle.write(chunk)
	return True

