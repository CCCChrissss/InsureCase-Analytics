from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services import embedding_service
from backend.scripts import run_semantic_query_trial

DEFAULT_DB_PATH = run_semantic_query_trial.DEFAULT_DB_PATH
DEFAULT_JSON_OUT = PROJECT_ROOT / "outputs" / "local_bge_query_suggestion_experiment_v1.json"
QUERY_SET_NAME = "benchmark-v1-suggestions-v1"

QUERY_SUGGESTIONS_V1: tuple[dict[str, str], ...] = (
    {
        "original_query": "除外責任",
        "suggested_query": "保險公司依除外責任條款拒絕理賠是否合理",
        "rule_id": "clarify_clause_effect",
        "explanation": "補足條款名稱、拒賠行為與合理性判斷。",
    },
    {
        "original_query": "必要性醫療",
        "suggested_query": "住院手術或醫療處置是否符合醫療必要性",
        "rule_id": "clarify_medical_action",
        "explanation": "補足可能接受審查的住院、手術與醫療處置。",
    },
    {
        "original_query": "癌症",
        "suggested_query": "癌症診斷及癌症保險金給付爭議",
        "rule_id": "clarify_diagnosis_and_benefit",
        "explanation": "補足癌症診斷與保險金給付兩個常見搜尋意圖。",
    },
    {
        "original_query": "住院",
        "suggested_query": "是否符合保單住院定義與住院必要性",
        "rule_id": "clarify_definition_and_necessity",
        "explanation": "補足保單定義與住院必要性判斷。",
    },
    {
        "original_query": "失能",
        "suggested_query": "被保險人失能程度及失能保險金認定",
        "rule_id": "clarify_degree_and_benefit",
        "explanation": "補足失能程度、被保險人與給付認定。",
    },
    {
        "original_query": "承保範圍",
        "suggested_query": "保險事故或醫療項目是否屬於保單承保範圍",
        "rule_id": "clarify_covered_object",
        "explanation": "補足需要判斷是否受保障的事故或醫療項目。",
    },
    {
        "original_query": "違反告知義務",
        "suggested_query": "要保人隱匿病史保險公司解除契約",
        "rule_id": "clarify_actor_action_effect",
        "explanation": "補足要保人、隱匿病史與解除契約的法律效果。",
    },
    {
        "original_query": "理賠金額",
        "suggested_query": "保險公司理賠金額計算是否符合保單條款",
        "rule_id": "clarify_calculation_basis",
        "explanation": "補足理賠計算行為與保單條款依據。",
    },
    {
        "original_query": "手術認定",
        "suggested_query": "醫療處置是否符合保單手術定義",
        "rule_id": "clarify_procedure_definition",
        "explanation": "補足醫療處置與保單手術定義的判斷關係。",
    },
    {
        "original_query": "投保前疾病",
        "suggested_query": "疾病是否在投保前已存在而不予理賠",
        "rule_id": "clarify_timing_and_effect",
        "explanation": "補足疾病存在時間與拒賠效果。",
    },
    {
        "original_query": "保單停效",
        "suggested_query": "未繳保費導致保單停效期間發生保險事故",
        "rule_id": "clarify_cause_and_timing",
        "explanation": "補足停效原因及事故發生時點。",
    },
    {
        "original_query": "意外事故",
        "suggested_query": "事故是否符合外來突發非疾病的意外事故定義",
        "rule_id": "clarify_accident_definition",
        "explanation": "補足外來性、突發性與非疾病等判斷要件。",
    },
    {
        "original_query": "條款怎麼解釋",
        "suggested_query": "保險契約條款有疑義時應如何解釋",
        "rule_id": "clarify_contract_context",
        "explanation": "補足保險契約與條款疑義的情境。",
    },
    {
        "original_query": "業務招攬",
        "suggested_query": "業務員招攬過程未充分說明保單",
        "rule_id": "clarify_solicitation_defect",
        "explanation": "補足招攬過程、保單說明與可能瑕疵。",
    },
    {
        "original_query": "豁免保費",
        "suggested_query": "被保險人失能或罹癌後免繳保險費",
        "rule_id": "clarify_trigger_and_effect",
        "explanation": "補足失能或癌症等啟動條件與免繳效果。",
    },
)


def validate_suggestions(specs: tuple[dict[str, str], ...] = QUERY_SUGGESTIONS_V1) -> None:
    benchmark_queries = tuple(run_semantic_query_trial.BENCHMARK_QUERY_SETS["benchmark-v1"])
    original_queries = tuple(spec.get("original_query", "").strip() for spec in specs)
    suggested_queries = tuple(spec.get("suggested_query", "").strip() for spec in specs)

    if original_queries != benchmark_queries:
        raise ValueError("Suggestion specs must match benchmark-v1 queries and order exactly.")
    if len(set(suggested_queries)) != len(suggested_queries):
        raise ValueError("Suggested queries must be unique.")

    for spec in specs:
        missing = [key for key in ("original_query", "suggested_query", "rule_id", "explanation") if not spec.get(key, "").strip()]
        if missing:
            raise ValueError(f"Suggestion spec is missing required fields: {missing}")
        if spec["original_query"].strip() == spec["suggested_query"].strip():
            raise ValueError(f"Suggested query must differ from original: {spec['original_query']}")


def make_read_only_connection_factory(db_path: Path):
    database_uri = f"{db_path.resolve().as_uri()}?mode=ro"

    def make_connection() -> sqlite3.Connection:
        connection = sqlite3.connect(database_uri, uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    return make_connection


def run_suggestion_trial(
    db_path: Path,
    *,
    limit: int = 5,
    min_score: float = 0.0,
    include_text: bool = True,
) -> dict[str, Any]:
    validate_suggestions()
    if limit <= 0:
        raise ValueError("limit must be greater than 0.")

    original_connect = embedding_service.connect
    embedding_service.connect = make_read_only_connection_factory(db_path)
    try:
        query_results = []
        for spec in QUERY_SUGGESTIONS_V1:
            result = embedding_service.semantic_search(
                spec["suggested_query"],
                limit=limit,
                model_name=embedding_service.LOCAL_BGE_MODEL_NAME,
                provider_name=embedding_service.LOCAL_BGE_PROVIDER_NAME,
                min_score=min_score,
            )
            query_results.append(
                {
                    **run_semantic_query_trial.compact_semantic_result(result, include_text=include_text),
                    **spec,
                }
            )
    finally:
        embedding_service.connect = original_connect

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database": str(db_path.resolve()),
        "embedding_provider": embedding_service.LOCAL_BGE_PROVIDER_NAME,
        "embedding_model": embedding_service.LOCAL_BGE_MODEL_NAME,
        "query_set": QUERY_SET_NAME,
        "candidate_scope": query_results[0]["total_candidates"] if query_results else 0,
        "queries": query_results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the explainable benchmark-v1 query suggestion experiment with local BGE."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="SQLite trial database path.")
    parser.add_argument("--limit", type=int, default=5, help="Top result count per suggested query.")
    parser.add_argument("--min-score", type=float, default=0.0, help="Minimum cosine similarity score.")
    parser.add_argument("--no-text", action="store_true", help="Exclude truncated chunk text from JSON output.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT, help="JSON result output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = run_semantic_query_trial.resolve_project_path(args.db)
    if not db_path.exists():
        raise SystemExit(f"Trial DB not found: {db_path}")

    try:
        payload = run_suggestion_trial(
            db_path,
            limit=args.limit,
            min_score=args.min_score,
            include_text=not args.no_text,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error

    json_output = json.dumps(payload, ensure_ascii=False, indent=2)
    output_path = run_semantic_query_trial.resolve_project_path(args.json_out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(f"{json_output}\n", encoding="utf-8")

    run_semantic_query_trial.configure_stdout_utf8()
    print(
        json.dumps(
            {
                "output": str(output_path),
                "query_set": payload["query_set"],
                "queries": len(payload["queries"]),
                "results": sum(len(item["top"]) for item in payload["queries"]),
                "embedding_provider": payload["embedding_provider"],
                "embedding_model": payload["embedding_model"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
