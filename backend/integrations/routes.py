import hmac

from flask import Blueprint, current_app, jsonify, request

from backend.events.repository import get_event, update_analysis

integrations_bp = Blueprint("integrations", __name__)


@integrations_bp.post("/api/n8n/analysis-result")
def receive_analysis_result():
	expected_token = current_app.config["N8N_WEBHOOK_TOKEN"]
	received_token = request.headers.get("X-Webhook-Token", "")
	if not expected_token or not hmac.compare_digest(received_token, expected_token):
		return jsonify(error="Token de webhook inválido."), 401

	payload = request.get_json(silent=True) or {}
	event_id = str(payload.get("event_id", ""))
	status = payload.get("status")
	if not event_id or status not in {"success", "error"}:
		return jsonify(error="Resultado de análisis inválido."), 400
	if get_event(event_id) is None:
		return jsonify(error="Evento no encontrado."), 404

	if status == "success":
		report_text = str(payload.get("report_text", "")).strip()
		if not report_text:
			return jsonify(error="El reporte está vacío."), 400
		update_analysis(event_id, "done", report_text)
	else:
		update_analysis(event_id, "failed")
	return jsonify(ok=True)
