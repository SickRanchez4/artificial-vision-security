"""Configuración del backend obtenida desde variables de entorno."""

import os


def _get_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes"}


class Config:
    SECRET_KEY = os.getenv("APP_SECRET_KEY", "clave-solo-para-demo-local")
    SQL_SERVER_CONNECTION_STRING = os.getenv(
        "SQL_SERVER_CONNECTION_STRING",
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost;DATABASE=ArtificialVisionSecurity;"
        "Trusted_Connection=yes;TrustServerCertificate=yes;",
    )
    APP_USERNAME = os.getenv("APP_USERNAME", "estudiante@uagrm.bo")
    APP_PASSWORD = os.getenv("APP_PASSWORD", "password")
    APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5000")
    VIDEO_SOURCE_PATH = os.getenv("VIDEO_SOURCE_PATH", "")
    YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "yolov8s-worldv2.pt")
    DETECTION_CONFIDENCE = 0.70
    DETECTION_COOLDOWN_SECONDS = 20
    DETECTION_FPS = float(os.getenv("DETECTION_FPS", "3"))
    N8N_ANALYSIS_WEBHOOK_URL = os.getenv("N8N_ANALYSIS_WEBHOOK_URL", "")
    N8N_CHAT_WEBHOOK_URL = os.getenv("N8N_CHAT_WEBHOOK_URL", "")
    N8N_WEBHOOK_TOKEN = os.getenv("N8N_WEBHOOK_TOKEN", "")
    N8N_TIMEOUT_SECONDS = int(os.getenv("N8N_TIMEOUT_SECONDS", "30"))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _get_bool("SESSION_COOKIE_SECURE")
