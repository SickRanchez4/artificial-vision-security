"""Cliente HTTP para los webhooks externos de n8n."""

import base64
from datetime import datetime

import requests
from flask import current_app

from backend.events.repository import update_analysis


def send_event_for_analysis(event_id: str, detected_at: datetime, detection: dict, image: bytes) -> None:
    webhook_url = current_app.config["N8N_ANALYSIS_WEBHOOK_URL"]
    if not webhook_url:
        update_analysis(event_id, "failed")
        return

    payload = {
        "event_id": event_id,
        "detected_at": detected_at.isoformat(),
        "weapon_class": detection["weapon_class"],
        "confidence": round(float(detection["confidence"]), 4),
        "image_base64": base64.b64encode(image).decode("ascii"),
        "callback_url": f'{current_app.config["APP_BASE_URL"]}/api/n8n/analysis-result',
    }
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=current_app.config["N8N_TIMEOUT_SECONDS"],
        )
        response.raise_for_status()
    except requests.RequestException:
        update_analysis(event_id, "failed")


def ask_chat(question: str, conversation_id: str) -> str:
    webhook_url = current_app.config["N8N_CHAT_WEBHOOK_URL"]
    if not webhook_url:
        raise requests.RequestException("Webhook de chat no configurado")
    response = requests.post(
        webhook_url,
        json={"conversation_id": conversation_id, "question": question},
        timeout=current_app.config["N8N_TIMEOUT_SECONDS"],
    )
    response.raise_for_status()
    answer = str(response.json().get("answer", "")).strip()
    if not answer:
        raise requests.RequestException("n8n devolvió una respuesta vacía")
    return answer