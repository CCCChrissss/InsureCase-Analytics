from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "backend" / "data" / "insurance_cases.db"
DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def parse_csv_env(value: str | None, default: tuple[str, ...]) -> list[str]:
    if value is None:
        return list(default)
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or list(default)


DATABASE_PATH = resolve_project_path(os.environ.get("INSURANCE_CASES_DB_PATH", DEFAULT_DATABASE_PATH))
CORS_ORIGINS = parse_csv_env(os.environ.get("BACKEND_CORS_ORIGINS"), DEFAULT_CORS_ORIGINS)
