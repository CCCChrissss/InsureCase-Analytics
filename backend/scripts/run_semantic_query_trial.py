from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services import embedding_service

DEFAULT_DB_PATH = PROJECT_ROOT / "backend" / "data" / "insurance_cases_hf_trial.db"
DEFAULT_PROVIDER = "huggingface"
DEFAULT_MODEL = "BAAI/bge-large-zh-v1.5"
DEFAULT_QUERY = "除外責任"
BENCHMARK_QUERY_SETS = {
    "benchmark-v1": (
        "除外責任",
        "必要性醫療",
        "癌症",
        "住院",
        "失能",
        "承保範圍",
        "違反告知義務",
        "理賠金額",
        "手術認定",
        "投保前疾病",
        "保單停效",
        "意外事故",
        "條款怎麼解釋",
        "業務招攬",
        "豁免保費",
    )
}


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def truncate_text(value: str | None, *, limit: int = 160) -> str:
    compact = " ".join((value or "").split())
    return compact if len(compact) <= limit else f"{compact[:limit]}..."


def make_connection_factory(db_path: Path):
    def make_connection() -> sqlite3.Connection:
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    return make_connection


def compact_semantic_result(result: dict[str, Any], *, include_text: bool) -> dict[str, Any]:
    top_items: list[dict[str, Any]] = []
    for rank, item in enumerate(result["items"], start=1):
        row = {
            "rank": rank,
            "case_number": item["case_number"],
            "dispute_type": item["dispute_type"],
            "score": item["score"],
            "chunk_id": item["chunk_id"],
            "case_id": item["case_id"],
            "section_hint": item["section_hint"],
            "chunk_index": item["chunk_index"],
        }
        if include_text:
            row["chunk_text"] = truncate_text(item.get("chunk_text"))
        top_items.append(row)

    return {
        "query": result["query"],
        "embedding_model": result["embedding_model"],
        "total_candidates": result["total_candidates"],
        "top": top_items,
    }


def resolve_queries(explicit_queries: list[str] | None, query_set: str | None) -> list[str]:
    if explicit_queries and query_set:
        raise ValueError("Use either --query or --query-set, not both.")
    if query_set:
        return list(BENCHMARK_QUERY_SETS[query_set])
    return explicit_queries or [DEFAULT_QUERY]


def build_markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Hugging Face Semantic Query Trial",
        "",
        f"- Created at: `{payload['created_at']}`",
        f"- Database: `{payload['database']}`",
        f"- Embedding provider: `{payload['embedding_provider']}`",
        f"- Embedding model: `{payload['embedding_model']}`",
        f"- Query set: `{payload['query_set']}`",
        "",
        "This report uses Hugging Face to generate a query embedding, then compares it with stored trial chunk embeddings.",
        "It consumes API quota and does not modify the source database.",
        "",
    ]

    for query_result in payload["queries"]:
        lines.extend(
            [
                f"## Query: `{query_result['query']}`",
                "",
                f"- Total candidates: `{query_result['total_candidates']}`",
                "",
                "| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |",
                "| ---: | ---: | --- | --- | --- | --- | ---: |",
            ]
        )
        for item in query_result["top"]:
            lines.append(
                "| {rank} | {score} | `{case_number}` | {dispute_type} | `{chunk_id}` | {section_hint} | {chunk_index} |".format(
                    rank=item["rank"],
                    score=item["score"],
                    case_number=item["case_number"],
                    dispute_type=item["dispute_type"] or "",
                    chunk_id=item["chunk_id"],
                    section_hint=item["section_hint"] or "",
                    chunk_index=item["chunk_index"],
                )
            )
        lines.append("")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a small Hugging Face query-to-document semantic search trial on a SQLite trial DB."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="SQLite trial database path.")
    parser.add_argument("--query", action="append", dest="queries", help="Query text. Can be repeated.")
    parser.add_argument(
        "--query-set",
        choices=sorted(BENCHMARK_QUERY_SETS),
        default=None,
        help="Run a predefined query benchmark set.",
    )
    parser.add_argument("--provider", default=DEFAULT_PROVIDER, help="Embedding provider name.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Embedding model name.")
    parser.add_argument("--limit", type=int, default=5, help="Top result count per query.")
    parser.add_argument("--min-score", type=float, default=0.0, help="Minimum cosine similarity score.")
    parser.add_argument("--include-text", action="store_true", help="Include truncated chunk text in JSON output.")
    parser.add_argument("--out", type=Path, default=None, help="Optional Markdown report output path.")
    parser.add_argument("--json-out", type=Path, default=None, help="Optional JSON result output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = resolve_project_path(args.db)
    if not db_path.exists():
        raise SystemExit(f"Trial DB not found: {db_path}")
    if args.limit <= 0:
        raise SystemExit("--limit must be greater than 0.")

    try:
        queries = resolve_queries(args.queries, args.query_set)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    provider = args.provider.strip().lower()
    if provider in {"huggingface", "hf"} and not (
        os.environ.get("EMBEDDING_API_KEY", "").strip() or os.environ.get("HF_TOKEN", "").strip()
    ):
        raise SystemExit(
            "Missing EMBEDDING_API_KEY or HF_TOKEN. Set the Hugging Face token in your shell environment before running this trial."
        )

    original_connect = embedding_service.connect
    embedding_service.connect = make_connection_factory(db_path)
    try:
        query_results = [
            compact_semantic_result(
                embedding_service.semantic_search(
                    query,
                    limit=args.limit,
                    model_name=args.model,
                    provider_name=args.provider,
                    min_score=args.min_score,
                ),
                include_text=args.include_text,
            )
            for query in queries
        ]
    finally:
        embedding_service.connect = original_connect

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database": str(db_path),
        "embedding_provider": args.provider,
        "embedding_model": args.model,
        "query_set": args.query_set or ("custom" if args.queries else "default"),
        "queries": query_results,
    }
    json_output = json.dumps(payload, ensure_ascii=False, indent=2)
    print(json_output)

    if args.json_out:
        json_out_path = resolve_project_path(args.json_out)
        json_out_path.parent.mkdir(parents=True, exist_ok=True)
        json_out_path.write_text(f"{json_output}\n", encoding="utf-8")

    if args.out:
        out_path = resolve_project_path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(build_markdown_report(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
