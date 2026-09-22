"""Persistencia de sesiones de análisis de video (archivo subido / cámara)."""

from datetime import datetime, timezone
from uuid import UUID

from backend.db import get_connection


def create_session(session_id: UUID, source_type: str, source_ref: str | None = None) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO video_sessions (id, source_type, source_ref, started_at, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            (str(session_id), source_type, source_ref, datetime.now(timezone.utc).isoformat()),
        )


def close_session(session_id: str) -> None:
    """Marca la sesión como finalizada correctamente (fin natural o manual)."""
    _end_session(session_id, status="finished", error_message=None)


def mark_session_error(session_id: str, error_message: str) -> None:
    """Marca la sesión como fallida con un mensaje de error para el usuario."""
    _end_session(session_id, status="error", error_message=error_message)


def get_active_session() -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, source_type, source_ref, started_at, status, error_message
            FROM video_sessions WHERE status = 'active'
            ORDER BY started_at DESC LIMIT 1
            """
        ).fetchone()
        return dict(row) if row else None


def _end_session(session_id: str, status: str, error_message: str | None) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE video_sessions
            SET status = ?, error_message = ?, ended_at = ?
            WHERE id = ?
            """,
            (status, error_message, datetime.now(timezone.utc).isoformat(), session_id),
        )
