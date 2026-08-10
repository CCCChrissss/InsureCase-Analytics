from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from backend.scripts import run_summary_trial


def _create_case_db(db_path: Path, *, with_summary: bool = False) -> None:
    """Create the smallest schema needed for deterministic batch tests."""

    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE cases (
              case_id TEXT PRIMARY KEY,
              case_number TEXT NOT NULL,
              decision_date TEXT,
              dispute_type TEXT,
              decision_result TEXT
            );
            CREATE TABLE case_texts (
              case_id TEXT PRIMARY KEY,
              normalized_text TEXT,
              raw_text TEXT,
              normalized_text_chars INTEGER
            );
            """
        )
        for index, dispute_type in enumerate(("類型甲", "類型乙", "類型丙"), start=1):
            case_id = f"case_{index}"
            connection.execute(
                "INSERT INTO cases VALUES (?, ?, '115.01.01', ?, '全部');",
                (case_id, f"115年評字第{index:06d}號", dispute_type),
            )
            text = "案件內容。" * (220 + index)
            connection.execute(
                "INSERT INTO case_texts VALUES (?, ?, ?, ?);",
                (case_id, text, text, len(text)),
            )
        if with_summary:
            connection.execute(
                "CREATE TABLE case_ai_summaries (summary_id TEXT PRIMARY KEY, case_id TEXT NOT NULL);"
            )
            connection.execute("INSERT INTO case_ai_summaries VALUES ('summary_1', 'case_1');")


class _FakeProvider:
    """Stand in for Ollama so checkpoint tests remain local and deterministic."""

    def ensure_model_available(self) -> dict[str, Any]:
        return {"provider": "ollama_local", "model": "qwen3:4b"}

    def close(self) -> None:
        return None


def test_representative_selection_can_exclude_existing_ai_summaries(tmp_path: Path) -> None:
    db_path = tmp_path / "cases.db"
    _create_case_db(db_path, with_summary=True)

    with run_summary_trial.connect_read_only(db_path) as connection:
        cases = run_summary_trial.load_cases(
            connection,
            limit=3,
            exclude_existing_summaries=True,
        )

    assert [case["case_id"] for case in cases] == ["case_2", "case_3"]


def test_resume_keeps_successes_and_retries_only_failed_cases(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    db_path = tmp_path / "cases.db"
    output_path = tmp_path / "trial.json"
    _create_case_db(db_path)
    case_numbers = ["115年評字第000001號", "115年評字第000002號"]
    monkeypatch.setattr(run_summary_trial, "create_summary_provider", lambda **_: _FakeProvider())
    monkeypatch.setattr(run_summary_trial, "structure_document_text", lambda *_: {"sections": []})
    monkeypatch.setattr(run_summary_trial, "build_source_packets", lambda *_args, **_kwargs: [object()])

    first_calls: list[str] = []

    def first_generation(*, case_metadata: dict[str, Any], **_: Any) -> dict[str, Any]:
        first_calls.append(case_metadata["case_id"])
        if case_metadata["case_id"] == "case_2":
            raise RuntimeError("temporary failure")
        return {"case_id": case_metadata["case_id"], "case_number": case_metadata["case_number"]}

    monkeypatch.setattr(run_summary_trial, "generate_case_summary", first_generation)
    first_report = run_summary_trial.build_trial_report(
        db_path=db_path,
        output_path=output_path,
        limit=2,
        case_numbers=case_numbers,
        model_name="qwen3:4b",
        base_url="http://127.0.0.1:11434",
        timeout_seconds=240,
        num_ctx=8192,
        max_output_tokens=2048,
        max_section_chars=2000,
        dry_run=False,
    )

    checkpoint = run_summary_trial.load_resume_report(output_path)
    assert first_calls == ["case_1", "case_2"]
    assert len(checkpoint["results"]) == 1
    assert len(checkpoint["errors"]) == 1

    resumed_calls: list[str] = []

    def resumed_generation(*, case_metadata: dict[str, Any], **_: Any) -> dict[str, Any]:
        resumed_calls.append(case_metadata["case_id"])
        return {"case_id": case_metadata["case_id"], "case_number": case_metadata["case_number"]}

    monkeypatch.setattr(run_summary_trial, "generate_case_summary", resumed_generation)
    resumed_report = run_summary_trial.build_trial_report(
        db_path=db_path,
        output_path=output_path,
        limit=2,
        case_numbers=run_summary_trial.resume_case_numbers(first_report),
        model_name="qwen3:4b",
        base_url="http://127.0.0.1:11434",
        timeout_seconds=240,
        num_ctx=8192,
        max_output_tokens=2048,
        max_section_chars=2000,
        dry_run=False,
        resume_report=checkpoint,
    )

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert resumed_calls == ["case_2"]
    assert len(resumed_report["results"]) == 2
    assert resumed_report["errors"] == []
    assert persisted["results"] == resumed_report["results"]
