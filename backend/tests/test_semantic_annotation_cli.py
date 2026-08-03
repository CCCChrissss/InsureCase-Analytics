from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from backend.scripts import annotate_semantic_benchmark


def make_annotation(*, query: str = "除外責任", label: str = "", evidence: str = "") -> dict:
    return {
        "query": query,
        "rank": 1,
        "score": 0.62,
        "chunk_id": "chunk_current",
        "case_id": "case_a",
        "case_number": "114年評字第000001號",
        "dispute_type": "除外責任",
        "section_hint": "判斷理由",
        "chunk_index": 1,
        "chunk_text": "目前結果文字",
        "label": label,
        "evidence_summary": evidence,
    }


def test_parse_label_supports_shortcuts_and_full_names() -> None:
    assert annotate_semantic_benchmark.parse_label("r") == "relevant"
    assert annotate_semantic_benchmark.parse_label(" P ") == "partially_relevant"
    assert annotate_semantic_benchmark.parse_label("not_relevant") == "not_relevant"
    assert annotate_semantic_benchmark.parse_label("unknown") is None


def test_pending_indices_skip_completed_other_queries_and_session_skips() -> None:
    annotations = [
        make_annotation(),
        make_annotation(label="relevant", evidence="直接討論除外責任。"),
        make_annotation(query="癌症"),
    ]

    assert annotate_semantic_benchmark.pending_indices(annotations) == [0, 2]
    assert annotate_semantic_benchmark.pending_indices(annotations, query="除外責任") == [0]
    assert annotate_semantic_benchmark.pending_indices(annotations, skipped={0}) == [2]


def test_apply_annotation_requires_valid_label_and_evidence() -> None:
    annotation = make_annotation()

    annotate_semantic_benchmark.apply_annotation(
        annotation,
        label="relevant",
        evidence_summary=" 原文明確說明除外責任條款。 ",
    )

    assert annotation["label"] == "relevant"
    assert annotation["evidence_summary"] == "原文明確說明除外責任條款。"
    with pytest.raises(ValueError, match="Unsupported label"):
        annotate_semantic_benchmark.apply_annotation(annotation, label="maybe", evidence_summary="有關")
    with pytest.raises(ValueError, match="must not be empty"):
        annotate_semantic_benchmark.apply_annotation(annotation, label="relevant", evidence_summary=" ")


def test_save_annotation_payload_replaces_file_and_keeps_utf8(tmp_path: Path) -> None:
    path = tmp_path / "annotations.json"
    payload = {"annotator": "測試者", "annotations": [make_annotation()]}

    annotate_semantic_benchmark.save_annotation_payload(path, payload)

    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert not path.with_suffix(".json.tmp").exists()


def test_load_context_chunks_reads_adjacent_chunks_without_writing(tmp_path: Path) -> None:
    db_path = tmp_path / "trial.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE case_chunks (
              chunk_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              chunk_index INTEGER NOT NULL,
              section_hint TEXT,
              chunk_text TEXT NOT NULL
            );
            """
        )
        connection.executemany(
            "INSERT INTO case_chunks VALUES (?, 'case_a', ?, '判斷理由', ?);",
            [
                ("chunk_previous", 0, "前一段"),
                ("chunk_current", 1, "目前段落"),
                ("chunk_next", 2, "後一段"),
                ("chunk_far", 3, "較遠段落"),
            ],
        )

    rows = annotate_semantic_benchmark.load_context_chunks(db_path, make_annotation(), context_size=1)

    assert [row["chunk_id"] for row in rows] == ["chunk_previous", "chunk_current", "chunk_next"]
    assert not list(tmp_path.glob("trial.db-journal"))


def test_run_annotation_session_saves_completed_item(tmp_path: Path) -> None:
    annotations_path = tmp_path / "annotations.json"
    payload = {"annotator": "tester", "annotations": [make_annotation()]}
    annotate_semantic_benchmark.save_annotation_payload(annotations_path, payload)
    answers = iter(["r", "原文明確討論除外責任。"])

    progress = annotate_semantic_benchmark.run_annotation_session(
        payload,
        annotations_path=annotations_path,
        db_path=tmp_path / "missing.db",
        query=None,
        index=None,
        context_size=1,
        input_func=lambda _: next(answers),
        output_func=lambda _: None,
    )

    saved = json.loads(annotations_path.read_text(encoding="utf-8"))
    assert saved["annotations"][0]["label"] == "relevant"
    assert progress == {
        "total": 1,
        "completed": 1,
        "remaining": 0,
        "relevant": 1,
        "partially_relevant": 0,
        "not_relevant": 0,
    }
