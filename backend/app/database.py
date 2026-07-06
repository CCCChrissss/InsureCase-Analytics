from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.app.config import DATABASE_PATH, PROJECT_ROOT

DEFAULT_DB_PATH = DATABASE_PATH
SCHEMA_PATH = PROJECT_ROOT / "backend" / "schema.sql"


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def initialize_database(db_path: Path = DEFAULT_DB_PATH, schema_path: Path = SCHEMA_PATH) -> None:
    with connect(db_path) as connection:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
