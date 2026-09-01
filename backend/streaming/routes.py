from flask import Blueprint, Response, current_app

streaming_bp = Blueprint("streaming", __name__)


@streaming_bp.get("/api/stream")
def stream():
	pipeline = current_app.extensions["detection_pipeline"]

	def generate_frames():
		while True:
			frame, _ = pipeline.wait_for_frame()
			yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"

	status = "online" if pipeline.camera_online else "offline"
	return Response(
		generate_frames(),
		mimetype="multipart/x-mixed-replace; boundary=frame",
		headers={"X-Camera-Status": status, "Cache-Control": "no-store"},
	)
