"""Configuración del backend obtenida desde variables de entorno."""

import os
from pathlib import Path


def _get_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes"}


_BACKEND_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv("APP_SECRET_KEY", "clave-solo-para-demo-local")
    SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", str(_BACKEND_DIR / "avs.db"))
    APP_USERNAME = os.getenv("APP_USERNAME", "estudiante@uagrm.bo")
    APP_PASSWORD = os.getenv("APP_PASSWORD", "password")
    APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5000")
    VIDEO_UPLOAD_TMP_DIR = os.getenv("VIDEO_UPLOAD_TMP_DIR", str(_BACKEND_DIR / "_uploads"))
    # RF-2.2: tamaño máximo de archivo .mp4 subido (256 MB); Flask corta la
    # subida a este límite antes de que el handler la procese.
    MAX_CONTENT_LENGTH = 256 * 1024 * 1024
    YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "yolov8s-security.pt")
    # Umbral de confianza por clase:
    DETECTION_CONFIDENCE_WEAPON = 0.50
    DETECTION_CONFIDENCE_PERSON = 0.50

    DETECTION_FPS = float(os.getenv("DETECTION_FPS", "3"))
    # RF-1: cantidad de frames consecutivos con detección de arma exigidos
    # antes de considerarla una candidata a incidencia.
    CONFIRMATION_FRAMES = 5
    # RF-3: segundos de enfriamiento tras enviar una detección confirmada a
    # n8n, antes de aceptar un nuevo seguimiento.
    INCIDENT_COOLDOWN_SECONDS = 15
    N8N_ANALYSIS_WEBHOOK_URL = os.getenv("N8N_ANALYSIS_WEBHOOK_URL", "https://primary-production-0331.up.railway.app/webhook/analyze-image")
    N8N_CHAT_WEBHOOK_URL = os.getenv("N8N_CHAT_WEBHOOK_URL", "")
    N8N_TIMEOUT_SECONDS = int(os.getenv("N8N_TIMEOUT_SECONDS", "30"))
    # Modo debug: corta el registro de eventos (BD + n8n) para poder ajustar
    # la visualización de los recuadros sin generar datos. No borra nada
    # existente; solo evita nuevas inserciones mientras esté en True.
    DEBUG_DISABLE_EVENTS = _get_bool("DEBUG_DISABLE_EVENTS", False)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _get_bool("SESSION_COOKIE_SECURE")
