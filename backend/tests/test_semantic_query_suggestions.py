from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.app.services import embedding_service
from backend.scripts import run_semantic_query_suggestion_trial
from backend.scripts import run_semantic_query_trial


def test_suggestions_cover_benchmark_v1_in_order() -> None:
    run_semantic_query_suggestion_trial.validate_suggestions()

    specs = run_semantic_query_suggestion_trial.QUERY_SUGGESTIONS_V1
    originals = tuple(spec["original_query"] for spec in specs)
    suggestions = tuple(spec["suggested_query"] for spec in specs)

    assert originals == run_semantic_query_trial.BENCHMARK_QUERY_SETS["benchmark-v1"]
    assert len(specs) == 15
    assert len(set(suggestions)) == 15
    assert all(spec["rule_id"] and spec["explanation"] for spec in specs)


def test_validate_suggestions_rejects_unchanged_query() -> None:
    specs = list(run_semantic_query_suggestion_trial.QUERY_SUGGESTIONS_V1)
    specs[0] = {**specs[0], "suggested_query": specs[0]["original_query"]}

    with pytest.raises(ValueError, match="must differ"):
        run_semantic_query_suggestion_trial.validate_suggestions(tuple(specs))


def test_read_only_connection_factory_rejects_writes(tmp_path: Path) -> None:
    db_path = tmp_path / "trial.db"
    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()

    read_only_connection = run_semantic_query_suggestion_trial.make_read_only_connection_factory(db_path)()
    try:
        assert read_only_connection.execute("SELECT COUNT(*) FROM sample").fetchone()[0] == 0
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            read_only_connection.execute("INSERT INTO sample DEFAULT VALUES")
    finally:
        read_only_connection.close()


def test_run_suggestion_trial_uses_local_bge_and_preserves_metadata(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "trial.db"
    sqlite3.connect(db_path).close()
    calls = []

    def fake_semantic_search(query: str, **kwargs):
        calls.append((query, kwargs))
        return {
            "query": query,
            "embedding_model": kwargs["model_name"],
            "total_candidates": 1000,
            "items": [
                {
                    "case_number": "114年評字第000001號",
                    "dispute_type": "測試",
                    "score": 0.9,
                    "chunk_id": f"chunk_{len(calls)}",
                    "case_id": "case_1",
                    "section_hint": "判斷理由",
                    "chunk_index": 1,
                    "chunk_text": "測試段落",
                }
            ],
        }

    monkeypatch.setattr(embedding_service, "semantic_search", fake_semantic_search)

    payload = run_semantic_query_suggestion_trial.run_suggestion_trial(db_path, limit=1)

    assert len(calls) == 15
    assert all(call[1]["provider_name"] == embedding_service.LOCAL_BGE_PROVIDER_NAME for call in calls)
    assert all(call[1]["model_name"] == embedding_service.LOCAL_BGE_MODEL_NAME for call in calls)
    assert payload["embedding_provider"] == "local_bge"
    assert payload["embedding_model"] == "BAAI/bge-large-zh-v1.5-local"
    assert payload["candidate_scope"] == 1000
    assert payload["queries"][0]["original_query"] == "除外責任"
    assert payload["queries"][0]["query"] == payload["queries"][0]["suggested_query"]
    assert payload["queries"][0]["rule_id"] == "clarify_clause_effect"
