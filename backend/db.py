"""Acceso mínimo a SQL Server y creación del esquema inicial."""

from contextlib import contextmanager

import pyodbc
from flask import current_app
from werkzeug.security import generate_password_hash


@contextmanager
def get_connection():
    connection = pyodbc.connect(
        current_app.config["SQL_SERVER_CONNECTION_STRING"], timeout=5
    )
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
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            IF OBJECT_ID(N'dbo.users', N'U') IS NULL
            BEGIN
                CREATE TABLE dbo.users (
                    id INT IDENTITY(1, 1) NOT NULL PRIMARY KEY,
                    username NVARCHAR(100) NOT NULL UNIQUE,
                    password_hash NVARCHAR(255) NOT NULL
                );
            END;

            IF OBJECT_ID(N'dbo.detection_events', N'U') IS NULL
            BEGIN
                CREATE TABLE dbo.detection_events (
                    id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
                    detected_at DATETIMEOFFSET NOT NULL,
                    weapon_class NVARCHAR(32) NOT NULL,
                    confidence REAL NOT NULL,
                    image VARBINARY(MAX) NOT NULL,
                    analysis_status NVARCHAR(16) NOT NULL,
                    report_text NVARCHAR(MAX) NULL,
                    CONSTRAINT CK_detection_events_weapon_class
                        CHECK (weapon_class IN (N'firearm', N'knife')),
                    CONSTRAINT CK_detection_events_confidence
                        CHECK (confidence >= 0.7 AND confidence <= 1.0),
                    CONSTRAINT CK_detection_events_analysis_status
                        CHECK (analysis_status IN (N'pending', N'done', N'failed'))
                );
            END;
            """
        )

        username = current_app.config["APP_USERNAME"]
        password_hash = generate_password_hash(current_app.config["APP_PASSWORD"])
        cursor.execute(
            """
            IF NOT EXISTS (SELECT 1 FROM dbo.users WHERE username = ?)
                INSERT INTO dbo.users (username, password_hash) VALUES (?, ?);
            """,
            username,
            username,
            password_hash,
        )


def find_user_by_username(username: str):
    with get_connection() as connection:
        cursor = connection.cursor()
        row = cursor.execute(
            "SELECT id, username, password_hash FROM dbo.users WHERE username = ?",
            username,
        ).fetchone()
        if row is None:
            return None
        return {"id": row.id, "username": row.username, "password_hash": row.password_hash}
