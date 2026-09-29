"""Verificación de capturas de incidencias mediante OpenAI."""

import base64
import json
import logging
from datetime import datetime

from flask import current_app
from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Analiza la captura de seguridad para determinar si muestra una amenaza real con un arma.
Devuelve solamente un objeto JSON con is_real_incident (booleano), report_text,
suspects_number y suspects_description. Redacta el reporte en español.
No deduzcas identidad, intenciones ni detalles que no sean visibles.
Si no hay evidencia visual suficiente para confirmar una amenaza real,
is_real_incident debe ser false. Si es true, report_text debe describir
brevemente lo observado; usa null para datos de sospechosos no verificables."""


def verify_incident(detected_at: datetime, detection: dict, image: bytes) -> dict | None:
    """Devuelve el análisis validado o None si no se pudo verificar la captura."""
    api_key = current_app.config["OPENAI_API_KEY"]
    if not api_key:
        logger.error("OPENAI_API_KEY no configurada; no se puede analizar la captura.")
        return None

    image_url = f"data:image/jpeg;base64,{base64.b64encode(image).decode('ascii')}"
    metadata = (
        f"Fecha y hora: {detected_at.isoformat()}; "
        f"clase detectada: {detection['weapon_class']}; "
        f"confianza de YOLO: {float(detection['confidence']):.4f}. "
        "La detección de YOLO es preliminar: confirma visualmente el incidente."
    )
    try:
        client = OpenAI(api_key=api_key, max_retries=0)
        response = client.chat.completions.create(
            model=current_app.config["OPENAI_IMAGE_MODEL"],
            timeout=current_app.config["OPENAI_TIMEOUT_SECONDS"],
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": metadata},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]},
            ],
        )
    except OpenAIError:
        logger.exception("Fallo al analizar la captura con OpenAI.")
        return None

    content = response.choices[0].message.content if response.choices else None
    try:
        result = json.loads(content) if content else None
    except (TypeError, ValueError):
        result = None

    if not isinstance(result, dict) or type(result.get("is_real_incident")) is not bool:
        logger.error("Respuesta de análisis sin is_real_incident booleano válido.")
        return None
    if not result["is_real_incident"]:
        return {"is_real_incident": False}

    report_text = result.get("report_text")
    suspects_number = result.get("suspects_number")
    suspects_description = result.get("suspects_description")
    if (
        not isinstance(report_text, str) or not report_text.strip()
        or (suspects_number is not None and (type(suspects_number) is not int or suspects_number < 0))
        or (suspects_description is not None and not isinstance(suspects_description, str))
    ):
        logger.error("Respuesta de análisis con campos de reporte inválidos.")
        return None
    return {
        "is_real_incident": True,
        "report_text": report_text.strip(),
        "suspects_number": suspects_number,
        "suspects_description": suspects_description,
    }