"""Rutas de integraciones externas.

Spec 003: el resultado del análisis de n8n ya no llega por un callback
asíncrono; se obtiene de forma síncrona en la misma llamada al webhook de
análisis (ver `backend.integrations.n8n_client.verify_incident`). Este
blueprint queda sin rutas propias por ahora.
"""

from flask import Blueprint

integrations_bp = Blueprint("integrations", __name__)

