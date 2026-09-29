import json
import logging

from flask import Blueprint, current_app, jsonify, request
from openai import OpenAI, OpenAIError

from backend.chat.repository import clear_messages, list_messages, save_message
from backend.events.repository import get_incident_summary

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__)

SYSTEM_PROMPT = """
Eres un analista de seguridad experto especializado en la interpretación de eventos detectados por visión artificial.
Tu único objetivo es responder a las preguntas del usuario utilizando EXCLUSIVAMENTE la información contenida en el JSON de incidencias proporcionado.

REGLAS DE ACTUACIÓN:
1. Responde siempre en español con un tono claro, directo y profesional.
2. Basate estrictamente en los datos del JSON. Si la respuesta a la pregunta no se encuentra en el listado, responde únicamente: "No dispongo de esa información en los registros actuales."
3. No asumas, extrapoles ni inventes datos que no estén explícitamente presentes.
4. Cuando cites una incidencia, incluye detalles relevantes si están disponibles (ej. ID, timestamp, cámara/ubicación, tipo de amenaza o nivel de confianza).
"""

@chat_bp.get("/api/chat")
def get_history():
	conversation_id = str(request.args.get("conversation_id", "")).strip()
	if not conversation_id:
		return jsonify(error="La conversación es obligatoria."), 400
	return jsonify(messages=list_messages(conversation_id))


@chat_bp.delete("/api/chat")
def delete_history():
	conversation_id = str(request.args.get("conversation_id", "")).strip()
	if not conversation_id:
		return jsonify(error="La conversación es obligatoria."), 400
	clear_messages(conversation_id)
	return jsonify(ok=True)


@chat_bp.post("/api/chat")
def chat():
	payload = request.get_json(silent=True) or {}
	question = str(payload.get("question", "")).strip()
	conversation_id = str(payload.get("conversation_id", "")).strip()
	if not question or not conversation_id:
		return jsonify(error="La pregunta y la conversación son obligatorias."), 400

	incidents = get_incident_summary()
	if incidents:
		incidents_json = json.dumps(incidents, ensure_ascii=False, default=str)
	else:
		incidents_json = "No hay ninguna incidencia registrada."

	try:
		client = OpenAI(api_key=current_app.config["OPENAI_API_KEY"], max_retries=0)
		response = client.chat.completions.create(
			model=current_app.config["OPENAI_CHAT_MODEL"],
			timeout=current_app.config["OPENAI_TIMEOUT_SECONDS"],
			messages=[
				{"role": "system", "content": SYSTEM_PROMPT},
				{"role": "system", "content": f"Incidencias registradas:\n{incidents_json}"},
				{"role": "user", "content": question},
			],
		)
		answer = (response.choices[0].message.content or "").strip() if response.choices else ""
		if not answer:
			raise OpenAIError("Respuesta vacía de OpenAI")
	except OpenAIError:
		logger.exception("Fallo al consultar OpenAI para el chatbot de incidencias.")
		return jsonify(error="El asistente no está disponible. Intenta de nuevo."), 502

	save_message(conversation_id, "user", question)
	save_message(conversation_id, "assistant", answer)

	return jsonify(answer=answer)
