"""Acceso mínimo a SQLite y creación del esquema inicial."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import current_app
from werkzeug.security import generate_password_hash


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

            CREATE TABLE IF NOT EXISTS detection_events (
                id TEXT NOT NULL PRIMARY KEY,
                detected_at TEXT NOT NULL,
                weapon_class TEXT NOT NULL
                    CHECK (weapon_class IN ('weapon')),
                confidence REAL NOT NULL
                    CHECK (confidence >= 0.25 AND confidence <= 1.0),
                image BLOB NOT NULL,
                analysis_status TEXT NOT NULL
                    CHECK (analysis_status IN ('pending', 'done', 'failed')),
                report_text TEXT
            );
            """
        )

        username = current_app.config["APP_USERNAME"]
        password_hash = generate_password_hash(current_app.config["APP_PASSWORD"])
        connection.execute(
            "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )


def find_user_by_username(username: str):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "username": row["username"], "password_hash": row["password_hash"]}
