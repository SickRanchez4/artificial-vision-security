"""Acceso mínimo a SQLite y creación del esquema inicial."""

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import current_app
from werkzeug.security import generate_password_hash

logger = logging.getLogger(__name__)


@contextmanager
def get_connection():
    connection = sqlite3.connect(current_app.config["SQLITE_DB_PATH"], timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_database() -> None:
    """Crea las tablas del MVP y el usuario inicial cuando no existen."""
    Path(current_app.config["SQLITE_DB_PATH"]).parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS video_sessions (
                id TEXT NOT NULL PRIMARY KEY,
                source_type TEXT NOT NULL
                    CHECK (source_type IN ('upload', 'live')),
                source_ref TEXT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                status TEXT NOT NULL
                    CHECK (status IN ('active', 'finished', 'error')),
                error_message TEXT
            );
            """
        )

        _ensure_detection_events_table(connection)

        username = current_app.config["APP_USERNAME"]
        password_hash = generate_password_hash(current_app.config["APP_PASSWORD"])
        connection.execute(
            "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )


def _ensure_detection_events_table(connection: sqlite3.Connection) -> None:
    """Crea `detection_events` sin restricción de umbral mínimo sobre
    `confidence`: el filtrado por confianza ya lo hace el detector antes de
    llegar aquí (`DETECTION_CONFIDENCE_WEAPON`), y el registro solo ocurre
    una vez que vuelve la respuesta del webhook de n8n (RF-2.3/RF-2.5), así
    que no tiene sentido duplicar esa validación con un `CHECK` en el
    esquema.

    SQLite no permite quitar un `CHECK` existente con `ALTER TABLE`: si la
    tabla ya existe con esa restricción (de una versión anterior del
    esquema), se reconstruye sin ella, conservando todos los eventos.
    """
    schema = """
        CREATE TABLE detection_events (
            id TEXT NOT NULL PRIMARY KEY,
            detected_at TEXT NOT NULL,
            weapon_class TEXT NOT NULL
                CHECK (weapon_class IN ('weapon')),
            confidence REAL NOT NULL,
            image BLOB NOT NULL,
            analysis_status TEXT NOT NULL
                CHECK (analysis_status IN ('pending', 'done', 'failed')),
            report_text TEXT,
            suspects_number INTEGER,
            suspects_description TEXT
        )
    """

    existing = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'detection_events'"
    ).fetchone()

    if existing is None:
        connection.execute(schema)
        return

    if "confidence >=" not in existing["sql"]:
        return  # Ya no tiene el CHECK de umbral mínimo.

    logger.warning("Quitando el CHECK de umbral mínimo de confidence en detection_events.")
    connection.execute("ALTER TABLE detection_events RENAME TO detection_events_old")
    connection.execute(schema)
    old_rows = connection.execute("SELECT * FROM detection_events_old").fetchall()
    for row in old_rows:
        old_row = dict(row)
        connection.execute(
            """
            INSERT INTO detection_events
                (id, detected_at, weapon_class, confidence, image, analysis_status,
                 report_text, suspects_number, suspects_description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                old_row["id"],
                old_row["detected_at"],
                old_row["weapon_class"],
                old_row["confidence"],
                old_row["image"],
                old_row["analysis_status"],
                old_row.get("report_text"),
                old_row.get("suspects_number"),
                old_row.get("suspects_description"),
            ),
        )
    connection.execute("DROP TABLE detection_events_old")


def find_user_by_username(username: str):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "username": row["username"], "password_hash": row["password_hash"]}
