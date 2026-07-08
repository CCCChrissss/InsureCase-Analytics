from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.embedding_service import DEFAULT_DIMS
from backend.app.services.embedding_service import MODEL_NAME
from backend.app.services.embedding_service import build_chunk_embeddings


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


DEFAULT_DB_PATH = resolve_project_path(os.environ.get("INSURANCE_CASES_DB_PATH", "backend/data/insurance_cases.db"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local embeddings for case chunks.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--dims", type=int, default=DEFAULT_DIMS)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_chunk_embeddings(
        resolve_project_path(args.db),
        model_name=args.model,
        dims=args.dims,
        limit=args.limit,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["empty_chunk_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
