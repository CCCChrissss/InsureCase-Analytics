from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "backend" / "data" / "insurance_cases.db"
DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
DEFAULT_EMBEDDING_PROVIDER = "local"
DEFAULT_EMBEDDING_MODEL = "local_hashing_cjk_v1"
DEFAULT_EMBEDDING_DIMS = 384
DEFAULT_LOCAL_BGE_DEVICE = "auto"
DEFAULT_LOCAL_BGE_BATCH_SIZE = 4
DEFAULT_SUMMARY_PROVIDER = "ollama_local"
DEFAULT_SUMMARY_MODEL = "qwen3:4b"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_SUMMARY_REQUEST_TIMEOUT_SECONDS = 240
DEFAULT_SUMMARY_NUM_CTX = 8192
DEFAULT_SUMMARY_MAX_OUTPUT_TOKENS = 2048
DEFAULT_SUMMARY_SECTION_MAX_CHARS = 2000


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def parse_csv_env(value: str | None, default: tuple[str, ...]) -> list[str]:
    if value is None:
        return list(default)
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or list(default)


def parse_int_env(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    return int(value)


DATABASE_PATH = resolve_project_path(os.environ.get("INSURANCE_CASES_DB_PATH", DEFAULT_DATABASE_PATH))
CORS_ORIGINS = parse_csv_env(os.environ.get("BACKEND_CORS_ORIGINS"), DEFAULT_CORS_ORIGINS)
EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", DEFAULT_EMBEDDING_PROVIDER).strip() or DEFAULT_EMBEDDING_PROVIDER
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip() or DEFAULT_EMBEDDING_MODEL
EMBEDDING_DIMS = parse_int_env(os.environ.get("EMBEDDING_DIMS"), DEFAULT_EMBEDDING_DIMS)
LOCAL_BGE_DEVICE = os.environ.get("LOCAL_BGE_DEVICE", DEFAULT_LOCAL_BGE_DEVICE).strip().lower() or DEFAULT_LOCAL_BGE_DEVICE
LOCAL_BGE_BATCH_SIZE = parse_int_env(os.environ.get("LOCAL_BGE_BATCH_SIZE"), DEFAULT_LOCAL_BGE_BATCH_SIZE)
SUMMARY_PROVIDER = os.environ.get("SUMMARY_PROVIDER", DEFAULT_SUMMARY_PROVIDER).strip().lower() or DEFAULT_SUMMARY_PROVIDER
SUMMARY_MODEL = os.environ.get("SUMMARY_MODEL", DEFAULT_SUMMARY_MODEL).strip() or DEFAULT_SUMMARY_MODEL
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).strip() or DEFAULT_OLLAMA_BASE_URL
SUMMARY_REQUEST_TIMEOUT_SECONDS = parse_int_env(
    os.environ.get("SUMMARY_REQUEST_TIMEOUT_SECONDS"),
    DEFAULT_SUMMARY_REQUEST_TIMEOUT_SECONDS,
)
SUMMARY_NUM_CTX = parse_int_env(os.environ.get("SUMMARY_NUM_CTX"), DEFAULT_SUMMARY_NUM_CTX)
SUMMARY_MAX_OUTPUT_TOKENS = parse_int_env(
    os.environ.get("SUMMARY_MAX_OUTPUT_TOKENS"),
    DEFAULT_SUMMARY_MAX_OUTPUT_TOKENS,
)
SUMMARY_SECTION_MAX_CHARS = parse_int_env(
    os.environ.get("SUMMARY_SECTION_MAX_CHARS"),
    DEFAULT_SUMMARY_SECTION_MAX_CHARS,
)
