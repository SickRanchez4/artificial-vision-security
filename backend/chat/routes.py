import requests
from flask import Blueprint, jsonify, request

from backend.integrations.n8n_client import ask_chat

chat_bp = Blueprint("chat", __name__)


@chat_bp.post("/api/chat")
def chat():
	payload = request.get_json(silent=True) or {}
	question = str(payload.get("question", "")).strip()
	conversation_id = str(payload.get("conversation_id", "")).strip()
	if not question or not conversation_id:
		return jsonify(error="La pregunta y la conversación son obligatorias."), 400
	try:
		return jsonify(answer=ask_chat(question, conversation_id))
	except (requests.RequestException, ValueError):
		return jsonify(error="El asistente no está disponible. Intenta de nuevo."), 502
