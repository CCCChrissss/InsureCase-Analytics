from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.app.config import DATABASE_PATH

DEFAULT_DB_PATH = DATABASE_PATH


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection
