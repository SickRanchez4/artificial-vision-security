from io import BytesIO

from flask import Blueprint, jsonify, send_file

from backend.events.repository import get_event, get_event_image, list_events

events_bp = Blueprint("events", __name__)


@events_bp.get("/api/events")
def events_list():
	return jsonify(list_events())


@events_bp.get("/api/events/<uuid:event_id>")
def event_detail(event_id):
	event = get_event(str(event_id))
	if event is None:
		return jsonify(error="Evento no encontrado."), 404
	return jsonify(event)


@events_bp.get("/api/events/<uuid:event_id>/image")
def event_image(event_id):
	image = get_event_image(str(event_id))
	if image is None:
		return jsonify(error="Imagen no encontrada."), 404
	return send_file(BytesIO(image), mimetype="image/jpeg", max_age=0)
