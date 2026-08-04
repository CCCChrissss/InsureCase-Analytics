from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.scripts import build_chunk_embeddings


def test_parse_args_supports_resume_and_write_batch_size(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_chunk_embeddings.py",
            "--resume",
            "--limit",
            "100",
            "--write-batch-size",
            "25",
        ],
    )

    args = build_chunk_embeddings.parse_args()

    assert args.resume is True
    assert args.limit == 100
    assert args.write_batch_size == 25


def test_main_reports_batch_progress_to_stderr(monkeypatch, tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "trial.db"
    captured_kwargs = {}

    def fake_build(selected_db_path: Path, **kwargs):
        captured_kwargs.update(kwargs)
        kwargs["progress_callback"](
            {
                "batch": 1,
                "batch_chunks": 25,
                "processed_chunks": 25,
                "selected_chunks": 100,
                "total_embeddings_in_table": 1025,
            }
        )
        return {
            "database": str(selected_db_path),
            "empty_chunk_count": 0,
            "total_embeddings_in_table": 1100,
        }

    monkeypatch.setattr(build_chunk_embeddings, "build_chunk_embeddings", fake_build)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_chunk_embeddings.py",
            "--db",
            str(db_path),
            "--resume",
            "--limit",
            "100",
            "--write-batch-size",
            "25",
        ],
    )

    build_chunk_embeddings.main()
    output = capsys.readouterr()
    progress = json.loads(output.err.strip())
    report = json.loads(output.out)

    assert captured_kwargs["resume"] is True
    assert captured_kwargs["limit"] == 100
    assert captured_kwargs["write_batch_size"] == 25
    assert callable(captured_kwargs["progress_callback"])
    assert progress["event"] == "embedding_batch"
    assert progress["processed_chunks"] == 25
    assert report["total_embeddings_in_table"] == 1100
