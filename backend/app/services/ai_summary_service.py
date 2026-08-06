from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping

from backend.app.database import connect


AI_SUMMARY_TABLE = "case_ai_summaries"
REVIEW_STATUSES = {"unreviewed", "approved", "rejected"}

# Scripts and tests use the same DDL as the checked-in schema. Keeping this
# statement here lets a trial DB be migrated explicitly without making a GET
# request mutate the database as a side effect.
CREATE_AI_SUMMARY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS case_ai_summaries (
  summary_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  generation_json TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  source_sha256 TEXT NOT NULL,
  review_status TEXT NOT NULL DEFAULT 'unreviewed'
    CHECK(review_status IN ('unreviewed', 'approved', 'rejected')),
  reviewer TEXT,
  review_note TEXT,
  generated_at TEXT NOT NULL,
  reviewed_at TEXT,
  imported_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  UNIQUE(case_id, model, prompt_version, source_sha256)
);
CREATE INDEX IF NOT EXISTS idx_case_ai_summaries_case_status
  ON case_ai_summaries(case_id, review_status, generated_at DESC);
"""


class AiSummaryDataError(RuntimeError):
    """Raised when persisted AI-summary data does not satisfy the API contract."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1;",
        (table_name,),
    ).fetchone()
    return row is not None


def ensure_ai_summary_schema(connection: sqlite3.Connection) -> None:
    """Create the versioned AI-summary store during an explicit import step."""

    connection.executescript(CREATE_AI_SUMMARY_SCHEMA_SQL)


def make_summary_id(
    *,
    case_id: str,
    model: str,
    prompt_version: str,
    source_sha256: str,
) -> str:
    """Build a stable ID so importing the same generated version is idempotent."""

    identity = "\x1f".join((case_id, model, prompt_version, source_sha256))
    return f"aisum_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]}"


def _required_text(mapping: Mapping[str, Any], key: str, *, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AiSummaryDataError(f"{context}.{key} must be a non-empty string.")
    return value.strip()


def _required_mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AiSummaryDataError(f"{context} must be an object.")
    return value


def _validate_summary_payload(summary: Mapping[str, Any], *, context: str) -> None:
    for field in ("background", "applicant_position", "respondent_position", "decision_result"):
        _required_text(summary, field, context=context)
    for field in ("core_issues", "reasoning_points", "legal_references", "evidence"):
        if not isinstance(summary.get(field), list):
            raise AiSummaryDataError(f"{context}.{field} must be a list.")


def import_summary_report(
    connection: sqlite3.Connection,
    report: Mapping[str, Any],
) -> dict[str, Any]:
    """Import a validated trial report while preserving existing review decisions."""

    results = report.get("results")
    if not isinstance(results, list) or not results:
        raise AiSummaryDataError("report.results must be a non-empty list.")

    ensure_ai_summary_schema(connection)
    imported_at = utc_now_iso()
    inserted = 0
    updated = 0
    summary_ids: list[str] = []

    for index, raw_result in enumerate(results):
        context = f"report.results[{index}]"
        result = _required_mapping(raw_result, context=context)
        case_id = _required_text(result, "case_id", context=context)
        summary = _required_mapping(result.get("summary"), context=f"{context}.summary")
        generation = _required_mapping(result.get("generation"), context=f"{context}.generation")
        _validate_summary_payload(summary, context=f"{context}.summary")

        provider = _required_text(generation, "provider", context=f"{context}.generation")
        model = _required_text(generation, "model", context=f"{context}.generation")
        prompt_version = _required_text(generation, "prompt_version", context=f"{context}.generation")
        source_sha256 = _required_text(generation, "source_hash_sha256", context=f"{context}.generation")
        if len(source_sha256) != 64 or any(character not in "0123456789abcdefABCDEF" for character in source_sha256):
            raise AiSummaryDataError(f"{context}.generation.source_hash_sha256 must be a 64-character hex digest.")
        generated_at = _required_text(generation, "generated_at", context=f"{context}.generation")
        if generation.get("review_status") not in {None, "unreviewed"}:
            raise AiSummaryDataError(f"{context}.generation.review_status must be unreviewed during import.")
        if generation.get("failed_request_count") not in {None, 0}:
            raise AiSummaryDataError(f"{context} contains failed model requests and cannot be imported.")
        if generation.get("final_merge_fallback") is True:
            raise AiSummaryDataError(f"{context} used the final merge fallback and requires regeneration.")
        if generation.get("request_errors") not in (None, []):
            raise AiSummaryDataError(f"{context} contains model request errors and cannot be imported.")

        case_row = connection.execute("SELECT 1 FROM cases WHERE case_id = ?;", (case_id,)).fetchone()
        if case_row is None:
            raise AiSummaryDataError(f"{context}.case_id does not exist in the target database: {case_id}")

        summary_id = make_summary_id(
            case_id=case_id,
            model=model,
            prompt_version=prompt_version,
            source_sha256=source_sha256,
        )
        existed = connection.execute(
            "SELECT 1 FROM case_ai_summaries WHERE summary_id = ?;",
            (summary_id,),
        ).fetchone() is not None

        # Review columns are deliberately absent from the update clause. A
        # repeat import may refresh diagnostics but cannot erase human review.
        connection.execute(
            """
            INSERT INTO case_ai_summaries (
              summary_id, case_id, summary_json, generation_json,
              provider, model, prompt_version, source_sha256,
              review_status, generated_at, imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'unreviewed', ?, ?)
            ON CONFLICT(summary_id) DO UPDATE SET
              summary_json = excluded.summary_json,
              generation_json = excluded.generation_json,
              provider = excluded.provider,
              model = excluded.model,
              prompt_version = excluded.prompt_version,
              source_sha256 = excluded.source_sha256,
              generated_at = excluded.generated_at,
              imported_at = excluded.imported_at;
            """,
            (
                summary_id,
                case_id,
                json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
                json.dumps(generation, ensure_ascii=False, separators=(",", ":")),
                provider,
                model,
                prompt_version,
                source_sha256,
                generated_at,
                imported_at,
            ),
        )
        summary_ids.append(summary_id)
        if existed:
            updated += 1
        else:
            inserted += 1

    return {
        "processed": len(results),
        "inserted": inserted,
        "updated": updated,
        "summary_ids": summary_ids,
        "imported_at": imported_at,
    }


def decode_summary_json(raw_value: str, *, field_name: str, summary_id: str) -> dict[str, Any]:
    """Decode a stored JSON object with a summary-specific diagnostic message."""

    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise AiSummaryDataError(f"Stored {field_name} is invalid JSON for {summary_id}.") from exc
    if not isinstance(value, dict):
        raise AiSummaryDataError(f"Stored {field_name} must be an object for {summary_id}.")
    return value


def _row_to_api_item(row: sqlite3.Row) -> dict[str, Any]:
    summary_id = str(row["summary_id"])
    summary = decode_summary_json(row["summary_json"], field_name="summary_json", summary_id=summary_id)
    _validate_summary_payload(summary, context=f"stored summary {summary_id}")
    status = str(row["review_status"])
    return {
        "summary_id": summary_id,
        "case_id": row["case_id"],
        "summary": summary,
        "provider": row["provider"],
        "model": row["model"],
        "prompt_version": row["prompt_version"],
        "source_sha256": row["source_sha256"],
        "review_status": status,
        "official": status == "approved",
        "generated_at": row["generated_at"],
        "reviewed_at": row["reviewed_at"],
    }


def get_case_ai_summary(case_id: str) -> dict[str, Any] | None:
    """Prefer an approved version; otherwise return the latest unreviewed trial."""

    with connect() as connection:
        if not table_exists(connection, AI_SUMMARY_TABLE):
            return None
        row = connection.execute(
            """
            SELECT summary_id, case_id, summary_json, provider, model,
                   prompt_version, source_sha256, review_status,
                   generated_at, reviewed_at
            FROM case_ai_summaries
            WHERE case_id = ?
              AND review_status IN ('approved', 'unreviewed')
            ORDER BY
              CASE review_status WHEN 'approved' THEN 0 ELSE 1 END,
              generated_at DESC,
              imported_at DESC
            LIMIT 1;
            """,
            (case_id,),
        ).fetchone()
    return _row_to_api_item(row) if row else None


def list_ai_summaries(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return compact rows for the local review queue."""

    if not table_exists(connection, AI_SUMMARY_TABLE):
        return []
    rows = connection.execute(
        """
        SELECT summaries.summary_id, summaries.case_id, cases.case_number,
               summaries.model, summaries.prompt_version, summaries.review_status,
               summaries.reviewer, summaries.review_note,
               summaries.generated_at, summaries.reviewed_at
        FROM case_ai_summaries AS summaries
        JOIN cases ON cases.case_id = summaries.case_id
        ORDER BY
          CASE summaries.review_status
            WHEN 'unreviewed' THEN 0
            WHEN 'approved' THEN 1
            ELSE 2
          END,
          summaries.generated_at DESC,
          cases.case_number;
        """
    ).fetchall()
    return [dict(row) for row in rows]


def find_ai_summary_for_review(
    connection: sqlite3.Connection,
    *,
    summary_id: str | None = None,
    case_number: str | None = None,
) -> sqlite3.Row | None:
    """Resolve exactly one summary version for CLI display or review."""

    if not table_exists(connection, AI_SUMMARY_TABLE):
        return None
    if bool(summary_id) == bool(case_number):
        raise ValueError("Provide exactly one of summary_id or case_number.")
    where_clause = "summaries.summary_id = ?" if summary_id else "cases.case_number = ?"
    value = summary_id or case_number
    return connection.execute(
        f"""
        SELECT summaries.*, cases.case_number
        FROM case_ai_summaries AS summaries
        JOIN cases ON cases.case_id = summaries.case_id
        WHERE {where_clause}
        ORDER BY summaries.generated_at DESC
        LIMIT 1;
        """,
        (value,),
    ).fetchone()


def review_ai_summary(
    connection: sqlite3.Connection,
    *,
    summary_id: str,
    status: str,
    reviewer: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Persist a local human decision without changing generated source evidence."""

    normalized_status = status.strip().lower()
    if normalized_status not in REVIEW_STATUSES:
        raise ValueError(f"Unsupported review status: {status}")
    normalized_reviewer = reviewer.strip()
    if not normalized_reviewer:
        raise ValueError("reviewer must not be blank.")
    reviewed_at = utc_now_iso() if normalized_status != "unreviewed" else None
    cursor = connection.execute(
        """
        UPDATE case_ai_summaries
        SET review_status = ?, reviewer = ?, review_note = ?, reviewed_at = ?
        WHERE summary_id = ?;
        """,
        (
            normalized_status,
            normalized_reviewer,
            note.strip() if note and note.strip() else None,
            reviewed_at,
            summary_id,
        ),
    )
    if cursor.rowcount != 1:
        raise AiSummaryDataError(f"AI summary not found: {summary_id}")
    return {
        "summary_id": summary_id,
        "review_status": normalized_status,
        "reviewer": normalized_reviewer,
        "review_note": note.strip() if note and note.strip() else None,
        "reviewed_at": reviewed_at,
    }
