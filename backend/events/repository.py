"""Persistencia y consulta de eventos de detección."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from backend.db import get_connection

WEAPON_LABELS = {"firearm": "Arma de fuego", "knife": "Arma blanca"}
STATUS_LABELS = {
    "pending": "Análisis: pendiente",
    "done": "Análisis: realizado",
    "failed": "Análisis: fallido",
}


def create_event(event_id: UUID, detected_at: datetime, weapon_class: str, confidence: float, image: bytes) -> None:
    with get_connection() as connection:
        connection.cursor().execute(
            """
            INSERT INTO dbo.detection_events
                (id, detected_at, weapon_class, confidence, image, analysis_status)
            VALUES (?, ?, ?, ?, ?, N'pending')
            """,
            str(event_id),
            detected_at,
            weapon_class,
            confidence,
            image,
        )


def has_recent_event(weapon_class: str, cooldown_seconds: int) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=cooldown_seconds)
    with get_connection() as connection:
        row = connection.cursor().execute(
            """
            SELECT TOP 1 1 FROM dbo.detection_events
            WHERE weapon_class = ? AND detected_at >= ?
            """,
            weapon_class,
            cutoff,
        ).fetchone()
        return row is not None


def list_events() -> list[dict]:
    with get_connection() as connection:
        rows = connection.cursor().execute(
            """
                 SELECT id, CONVERT(nvarchar(40), detected_at, 127) AS detected_at,
                     weapon_class, confidence, analysis_status, report_text
            FROM dbo.detection_events ORDER BY detected_at DESC
            """
        ).fetchall()
        return [_serialize_event(row) for row in rows]


def get_event(event_id: str) -> dict | None:
    with get_connection() as connection:
        row = connection.cursor().execute(
            """
                 SELECT id, CONVERT(nvarchar(40), detected_at, 127) AS detected_at,
                     weapon_class, confidence, analysis_status, report_text
            FROM dbo.detection_events WHERE id = ?
            """,
            event_id,
        ).fetchone()
        return _serialize_event(row) if row else None


def get_event_image(event_id: str) -> bytes | None:
    with get_connection() as connection:
        row = connection.cursor().execute(
            "SELECT image FROM dbo.detection_events WHERE id = ?", event_id
        ).fetchone()
        return bytes(row.image) if row else None


def update_analysis(event_id: str, status: str, report_text: str | None = None) -> bool:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE dbo.detection_events
            SET analysis_status = ?, report_text = ?
            WHERE id = ?
            """,
            status,
            report_text,
            event_id,
        )
        return cursor.rowcount > 0


def _serialize_event(row) -> dict:
    event_id = str(row.id)
    return {
        "id": event_id,
        "detected_at": row.detected_at,
        "weapon_class": row.weapon_class,
        "weapon_class_label": WEAPON_LABELS.get(row.weapon_class, row.weapon_class),
        "confidence": round(float(row.confidence), 4),
        "analysis_status": row.analysis_status,
        "analysis_status_label": STATUS_LABELS.get(row.analysis_status, row.analysis_status),
        "report_text": row.report_text,
        "image_url": f"/api/events/{event_id}/image",
    }