"""Rutas de autenticación mediante sesión de Flask."""

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash

from backend.db import find_user_by_username

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/api/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    user = find_user_by_username(username) if username and password else None

    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify(error="Credenciales inválidas."), 401

    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return jsonify(ok=True)


@auth_bp.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)
