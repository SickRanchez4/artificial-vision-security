"""Persistencia y consulta de eventos de detección."""

from datetime import datetime
from uuid import UUID

from backend.db import get_connection

WEAPON_LABELS = {"weapon": "Arma"}
STATUS_LABELS = {
    "pending": "Análisis: pendiente",
    "done": "Análisis: realizado",
    "failed": "Análisis: fallido",
}


def create_event(
    event_id: UUID,
    detected_at: datetime,
    weapon_class: str,
    confidence: float,
    image: bytes,
    analysis_status: str,
    report_text: str | None = None,
    suspects_number: int | None = None,
    suspects_description: str | None = None,
) -> None:
    """Persiste un evento de incidencia ya con su estado final de análisis
    (`done` o `failed`, RF-2.3/RF-2.5): no existe estado `pending` para
    incidencias de esta spec porque la respuesta de n8n se espera de forma
    síncrona antes de escribir en la base de datos.
    """
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO detection_events
                (id, detected_at, weapon_class, confidence, image, analysis_status,
                 report_text, suspects_number, suspects_description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(event_id),
                detected_at.isoformat(),
                weapon_class,
                confidence,
                image,
                analysis_status,
                report_text,
                suspects_number,
                suspects_description,
            ),
        )


def list_events() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, detected_at, weapon_class, confidence, analysis_status, report_text,
                   suspects_number, suspects_description
            FROM detection_events ORDER BY detected_at DESC
            """
        ).fetchall()
        return [_serialize_event(row) for row in rows]


def get_event(event_id: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, detected_at, weapon_class, confidence, analysis_status, report_text,
                   suspects_number, suspects_description
            FROM detection_events WHERE id = ?
            """,
            (event_id,),
        ).fetchone()
        return _serialize_event(row) if row else None


def get_event_image(event_id: str) -> bytes | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT image FROM detection_events WHERE id = ?", (event_id,)
        ).fetchone()
        return bytes(row["image"]) if row else None


def _serialize_event(row) -> dict:
    event_id = row["id"]
    return {
        "id": event_id,
        "detected_at": row["detected_at"],
        "weapon_class": row["weapon_class"],
        "weapon_class_label": WEAPON_LABELS.get(row["weapon_class"], row["weapon_class"]),
        "confidence": round(float(row["confidence"]), 4),
        "analysis_status": row["analysis_status"],
        "analysis_status_label": STATUS_LABELS.get(row["analysis_status"], row["analysis_status"]),
        "report_text": row["report_text"],
        "suspects_number": row["suspects_number"],
        "suspects_description": row["suspects_description"],
        "image_url": f"/api/events/{event_id}/image",
    }