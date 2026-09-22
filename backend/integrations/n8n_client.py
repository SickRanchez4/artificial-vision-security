"""Cliente HTTP para los webhooks externos de n8n."""

import json
import logging
from datetime import datetime

import requests
from flask import current_app

logger = logging.getLogger(__name__)


def verify_incident(event_id: str, detected_at: datetime, detection: dict, image: bytes) -> dict | None:
    """Envía la detección confirmada (RF-1.4) al webhook de análisis de n8n
    y espera de forma síncrona la respuesta del nodo "Respond to Webhook"
    (RF-2.1, RF-2.2).

    La imagen se envía como archivo real en `multipart/form-data` (no como
    texto base64), para que n8n la reciba automáticamente como binario en
    el nodo Webhook.

    Devuelve el resultado del análisis ya extraído (`is_real_incident`,
    `report_text`, `suspects_number`, `suspects_description`) cuando la
    respuesta trae un `is_real_incident` booleano válido; devuelve `None`
    ante cualquier fallo (sin webhook configurado, error de red, timeout,
    HTTP de error, JSON inválido o `is_real_incident` ausente/no booleano)
    — en todos esos casos el llamador debe tratarlo como análisis fallido
    (RF-2.5).
    """
    webhook_url = current_app.config["N8N_ANALYSIS_WEBHOOK_URL"]
    if not webhook_url:
        logger.warning("N8N_ANALYSIS_WEBHOOK_URL no configurado; no se puede verificar el incidente.")
        return None

    fields = {
        "event_id": event_id,
        "detected_at": detected_at.isoformat(),
        "weapon_class": detection["weapon_class"],
        "confidence": str(round(float(detection["confidence"]), 4)),
    }
    files = {
        "image": (f"{event_id}.jpg", image, "image/jpeg"),
    }
    try:
        response = requests.post(
            webhook_url,
            data=fields,
            files=files,
            timeout=current_app.config["N8N_TIMEOUT_SECONDS"],
        )
        response.raise_for_status()
        raw_result = response.json()
    except (requests.RequestException, ValueError):
        logger.exception("Fallo al verificar el incidente con n8n.")
        return None

    result = _extract_analysis_result(raw_result)
    if result is None or not isinstance(result.get("is_real_incident"), bool):
        logger.error("Respuesta de n8n sin 'is_real_incident' booleano válido: %r", raw_result)
        return None
    return result


def _extract_analysis_result(raw_result) -> dict | None:
    """Obtiene el JSON de análisis (`is_real_incident`, `report_text`, ...)
    de la respuesta del nodo "Respond to Webhook".

    El nodo de n8n envuelve ese JSON como texto dentro de una estructura de
    mensajes del asistente:
    `[[{"content": [{"type": "output_text", "text": "<json>"}], ...}]]`.
    Esta función soporta tanto ese formato anidado como una respuesta plana
    (`{"is_real_incident": ..., ...}`) directa, por si el flujo de n8n
    cambia de forma en el futuro.
    """
    if isinstance(raw_result, dict) and "is_real_incident" in raw_result:
        return raw_result

    # Desenvuelve listas anidadas hasta encontrar el mensaje con "content".
    node = raw_result
    while isinstance(node, list):
        if not node:
            return None
        node = node[0]

    if not isinstance(node, dict):
        return None

    for item in node.get("content", []):
        if not isinstance(item, dict) or item.get("type") != "output_text":
            continue
        text = item.get("text")
        if not isinstance(text, str):
            continue
        try:
            parsed = json.loads(text)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


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