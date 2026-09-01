"""Punto de entrada de la aplicación Flask."""

import sys
from pathlib import Path

# Al ejecutar `python app.py`, Python no agrega la raíz del proyecto al path.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, jsonify, request, session

from backend.auth.routes import auth_bp
from backend.chat.routes import chat_bp
from backend.config import Config
from backend.db import init_database
from backend.detection.pipeline import DetectionPipeline
from backend.events.routes import events_bp
from backend.integrations.routes import integrations_bp
from backend.streaming.routes import streaming_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    app.register_blueprint(auth_bp)
    app.register_blueprint(streaming_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(integrations_bp)
    app.register_blueprint(chat_bp)

    @app.before_request
    def require_api_session():
        public_webhook = request.path == "/api/n8n/analysis-result"
        if (
            request.path.startswith("/api/")
            and request.path != "/api/login"
            and not public_webhook
            and "user_id" not in session
        ):
            return jsonify(error="Debes iniciar sesión."), 401

    with app.app_context():
        init_database()

    pipeline = DetectionPipeline(app)
    app.extensions["detection_pipeline"] = pipeline
    pipeline.start()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, threaded=True)
