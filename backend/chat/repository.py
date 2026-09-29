"""Persistencia de mensajes del chatbot."""

from datetime import datetime, timezone

from backend.db import get_connection


def save_message(conversation_id: str, role: str, content: str) -> None:
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO chat_messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, datetime.now(timezone.utc).isoformat()),
        )


def list_messages(conversation_id: str) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT role, content, created_at FROM chat_messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def clear_messages(conversation_id: str) -> None:
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM chat_messages WHERE conversation_id = ?", (conversation_id,)
        )
