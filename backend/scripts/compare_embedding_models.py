from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.embedding_service import dot_product
from backend.app.services.embedding_service import unpack_vector

DEFAULT_DB_PATH = PROJECT_ROOT / "backend" / "data" / "insurance_cases_local_bge_trial.db"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "outputs" / "local_bge_embedding_comparison.md"
DEFAULT_LOCAL_MODEL = "local_hashing_cjk_v1"
DEFAULT_CANDIDATE_MODEL = "BAAI/bge-large-zh-v1.5-local"
DEFAULT_QUERIES = (
    "癌症保險金",
    "癌症",
    "住院日額",
    "除外責任",
    "必要性醫療",
    "醫療",
    "保單條款解釋",
    "條款",
)


@dataclass(frozen=True)
class CommonChunk:
    chunk_id: str
    case_id: str
    case_number: str
    decision_date: str | None
    dispute_type: str | None
    section_hint: str | None
    chunk_index: int
    chunk_text: str
    local_embedding: bytes
    local_dims: int
    candidate_embedding: bytes
    candidate_dims: int


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def normalize_text(text: str, *, limit: int = 180) -> str:
    compact = " ".join((text or "").split())
    return compact if len(compact) <= limit else f"{compact[:limit]}..."


def load_common_chunks(
    connection: sqlite3.Connection,
    *,
    local_model: str,
    candidate_model: str,
) -> list[CommonChunk]:
    rows = connection.execute(
        """
        SELECT case_chunks.chunk_id, case_chunks.case_id,
               case_chunks.chunk_index, case_chunks.section_hint,
               case_chunks.chunk_text,
               cases.case_number, cases.decision_date, cases.dispute_type,
               local_embeddings.embedding AS local_embedding,
               local_embeddings.embedding_dims AS local_dims,
               candidate_embeddings.embedding AS candidate_embedding,
               candidate_embeddings.embedding_dims AS candidate_dims
        FROM case_chunks
        JOIN cases ON cases.case_id = case_chunks.case_id
        JOIN chunk_embeddings AS local_embeddings
          ON local_embeddings.chunk_id = case_chunks.chunk_id
         AND local_embeddings.embedding_model = ?
        JOIN chunk_embeddings AS candidate_embeddings
          ON candidate_embeddings.chunk_id = case_chunks.chunk_id
         AND candidate_embeddings.embedding_model = ?
        ORDER BY case_chunks.case_id, case_chunks.chunk_index;
        """,
        (local_model, candidate_model),
    ).fetchall()
    return [
        CommonChunk(
            chunk_id=row["chunk_id"],
            case_id=row["case_id"],
            case_number=row["case_number"],
            decision_date=row["decision_date"],
            dispute_type=row["dispute_type"],
            section_hint=row["section_hint"],
            chunk_index=row["chunk_index"],
            chunk_text=row["chunk_text"],
            local_embedding=row["local_embedding"],
            local_dims=row["local_dims"],
            candidate_embedding=row["candidate_embedding"],
            candidate_dims=row["candidate_dims"],
        )
        for row in rows
    ]


def model_counts(connection: sqlite3.Connection) -> list[tuple[str, int, int]]:
    rows = connection.execute(
        """
        SELECT embedding_model, embedding_dims, COUNT(*) AS count
        FROM chunk_embeddings
        GROUP BY embedding_model, embedding_dims
        ORDER BY embedding_model, embedding_dims;
        """
    ).fetchall()
    return [(row["embedding_model"], int(row["embedding_dims"]), int(row["count"])) for row in rows]


def choose_anchor(chunks: Iterable[CommonChunk], query: str) -> CommonChunk | None:
    query = query.strip()
    if not query:
        return None
    for chunk in chunks:
        if query in chunk.chunk_text:
            return chunk
    return None


def rank_by_model(
    chunks: list[CommonChunk],
    *,
    anchor: CommonChunk,
    model: str,
    top: int,
    exclude_anchor: bool = True,
) -> list[dict[str, object]]:
    if model == "local":
        anchor_vector = unpack_vector(anchor.local_embedding, anchor.local_dims)
        embedding_attr = "local_embedding"
        dims_attr = "local_dims"
    elif model == "candidate":
        anchor_vector = unpack_vector(anchor.candidate_embedding, anchor.candidate_dims)
        embedding_attr = "candidate_embedding"
        dims_attr = "candidate_dims"
    else:
        raise ValueError(f"Unknown model selector: {model}")

    scored = []
    for chunk in chunks:
        if exclude_anchor and chunk.chunk_id == anchor.chunk_id:
            continue
        vector = unpack_vector(getattr(chunk, embedding_attr), getattr(chunk, dims_attr))
        score = dot_product(anchor_vector, vector)
        scored.append(
            {
                "chunk_id": chunk.chunk_id,
                "case_id": chunk.case_id,
                "case_number": chunk.case_number,
                "decision_date": chunk.decision_date,
                "dispute_type": chunk.dispute_type,
                "section_hint": chunk.section_hint,
                "chunk_index": chunk.chunk_index,
                "score": round(score, 4),
                "chunk_text": normalize_text(chunk.chunk_text),
            }
        )

    scored.sort(
        key=lambda item: (
            item["score"],
            item["decision_date"] or "",
            item["case_number"] or "",
            -int(item["chunk_index"]),
        ),
        reverse=True,
    )
    return scored[:top]


def compare_query(
    chunks: list[CommonChunk],
    *,
    query: str,
    top: int,
) -> dict[str, object]:
    anchor = choose_anchor(chunks, query)
    if anchor is None:
        return {
            "query": query,
            "status": "skipped",
            "reason": "No common chunk contains the exact query text.",
        }

    local_results = rank_by_model(chunks, anchor=anchor, model="local", top=top)
    candidate_results = rank_by_model(chunks, anchor=anchor, model="candidate", top=top)
    local_ids = {str(item["chunk_id"]) for item in local_results}
    candidate_ids = {str(item["chunk_id"]) for item in candidate_results}
    overlap = sorted(local_ids & candidate_ids)

    return {
        "query": query,
        "status": "compared",
        "anchor": {
            "chunk_id": anchor.chunk_id,
            "case_id": anchor.case_id,
            "case_number": anchor.case_number,
            "decision_date": anchor.decision_date,
            "dispute_type": anchor.dispute_type,
            "section_hint": anchor.section_hint,
            "chunk_index": anchor.chunk_index,
            "chunk_text": normalize_text(anchor.chunk_text),
        },
        "metrics": {
            "top_k": top,
            "overlap_count": len(overlap),
            "overlap_chunk_ids": overlap,
            "local_same_dispute_count": sum(
                1 for item in local_results if item["dispute_type"] == anchor.dispute_type
            ),
            "candidate_same_dispute_count": sum(
                1 for item in candidate_results if item["dispute_type"] == anchor.dispute_type
            ),
        },
        "local_results": local_results,
        "candidate_results": candidate_results,
    }


def build_report(
    *,
    db_path: Path,
    local_model: str,
    candidate_model: str,
    counts: list[tuple[str, int, int]],
    common_count: int,
    comparisons: list[dict[str, object]],
) -> str:
    compared_count = sum(1 for item in comparisons if item["status"] == "compared")
    skipped_count = len(comparisons) - compared_count
    lines = [
        "# Embedding Model Trial Comparison",
        "",
        "## 1. 目的",
        "",
        f"本報告比較 `{local_model}` 與 `{candidate_model}` 在共同 trial chunks 上的離線排序結果。",
        "比較重點不是宣稱模型已正式上線，而是確認不同 embedding model 可在同一批 chunks 上進行可追溯分析。",
        "",
        "## 2. 試跑資料",
        "",
        f"- 產生時間：`{datetime.now(timezone.utc).isoformat()}`",
        f"- Trial DB：`{db_path}`",
        f"- Local model：`{local_model}`",
        f"- Candidate model：`{candidate_model}`",
        f"- 共同 chunks：`{common_count}`",
        "",
        "目前 `chunk_embeddings` 模型分布：",
        "",
        "| embedding_model | dims | count |",
        "| --- | ---: | ---: |",
    ]
    for model, dims, count in counts:
        lines.append(f"| `{model}` | {dims} | {count} |")

    lines.extend(
        [
            "",
            "## 3. 比較方法",
            "",
            "本次只讀取 trial DB 已存在的 embeddings，不會呼叫外部 API。",
            "比較採用 anchor-based 方法：",
            "",
            f"1. 在同時擁有兩種 embeddings 的 {common_count} 個 chunks 中，尋找包含查詢詞的 anchor chunk。",
            "2. 使用同一個 anchor chunk 的 local 向量，比對其餘共同 chunks。",
            "3. 使用同一個 anchor chunk 的 BGE 向量，比對其餘共同 chunks。",
            "4. 比較兩種模型各自 Top results 的分數、爭議類型與命中段落。",
            "",
            "限制：這是 anchor-based 模型比較，不是完整的 query-to-document 評測。真實查詢詞應使用 run_semantic_query_trial.py 與人工 relevance 標註驗證。",
            "",
            "## 4. 結果摘要",
            "",
            f"- 已比較查詢詞：`{compared_count}`",
            f"- 無 anchor 而略過：`{skipped_count}`",
            "",
        ]
    )

    for comparison in comparisons:
        query = str(comparison["query"])
        lines.extend([f"### `{query}`", ""])
        if comparison["status"] != "compared":
            lines.extend([f"- 狀態：略過，原因：{comparison['reason']}", ""])
            continue

        anchor = comparison["anchor"]
        metrics = comparison["metrics"]
        lines.extend(
            [
                "Anchor chunk：",
                "",
                f"- chunk_id：`{anchor['chunk_id']}`",
                f"- 案號：`{anchor['case_number']}`",
                f"- 決定日期：`{anchor['decision_date']}`",
                f"- 爭議類型：`{anchor['dispute_type']}`",
                f"- section：`{anchor['section_hint']}`",
                f"- chunk_index：`{anchor['chunk_index']}`",
                f"- 片段：{anchor['chunk_text']}",
                "",
                "比較指標：",
                "",
                f"- Top {metrics['top_k']} overlap：`{metrics['overlap_count']}`",
                f"- Local Top {metrics['top_k']} 同爭議類型數：`{metrics['local_same_dispute_count']}`",
                f"- BGE Top {metrics['top_k']} 同爭議類型數：`{metrics['candidate_same_dispute_count']}`",
                "",
                "Local hashing Top results：",
                "",
                "| rank | score | 案號 | 爭議類型 | chunk | 片段 |",
                "| ---: | ---: | --- | --- | --- | --- |",
            ]
        )
        for index, item in enumerate(comparison["local_results"], start=1):
            lines.append(format_result_row(index, item))

        lines.extend(
            [
                "",
                "BGE Top results：",
                "",
                "| rank | score | 案號 | 爭議類型 | chunk | 片段 |",
                "| ---: | ---: | --- | --- | --- | --- |",
            ]
        )
        for index, item in enumerate(comparison["candidate_results"], start=1):
            lines.append(format_result_row(index, item))
        lines.append("")

    lines.extend(
        [
            "## 5. 初步結論",
            "",
            f"- `{candidate_model}` 與 SQLite 寫入流程可用共同 chunks 進行離線比較。",
            "- 本報告只代表目前共同樣本的 anchor-based 比較，不能宣稱全量搜尋品質已優於 local MVP。",
            "- 更接近使用者體驗的比較應執行固定 query benchmark，並完成人工 relevance 標註。",
            "- 正式 DB `backend/data/insurance_cases.db` 目前仍應維持 `local_hashing_cjk_v1`，等品質與成本評估後再決定是否全量重建。",
            "",
        ]
    )
    return "\n".join(lines)


def format_result_row(rank: int, item: dict[str, object]) -> str:
    snippet = str(item["chunk_text"]).replace("|", "\\|")
    dispute_type = str(item["dispute_type"] or "").replace("|", "\\|")
    return (
        f"| {rank} | {item['score']} | `{item['case_number']}` | "
        f"{dispute_type} | `{item['chunk_id']}` | {snippet} |"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare local and candidate embedding models on common chunks.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="SQLite trial database path.")
    parser.add_argument("--local-model", default=DEFAULT_LOCAL_MODEL, help="Baseline embedding model name.")
    parser.add_argument("--candidate-model", default=DEFAULT_CANDIDATE_MODEL, help="Candidate embedding model name.")
    parser.add_argument("--query", action="append", dest="queries", help="Query text. Can be repeated.")
    parser.add_argument("--top", type=int, default=5, help="Top results per model.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_PATH, help="Markdown report output path.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary to stdout.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = resolve_project_path(args.db)
    out_path = resolve_project_path(args.out)
    queries = tuple(args.queries) if args.queries else DEFAULT_QUERIES
    if args.top <= 0:
        raise SystemExit("--top must be greater than 0.")
    if not db_path.exists():
        raise SystemExit(f"Trial DB not found: {db_path}")

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        chunks = load_common_chunks(
            connection,
            local_model=args.local_model,
            candidate_model=args.candidate_model,
        )
        counts = model_counts(connection)

    if not chunks:
        raise SystemExit(
            f"No common chunks found for models {args.local_model!r} and {args.candidate_model!r} in {db_path}."
        )

    comparisons = [compare_query(chunks, query=query, top=args.top) for query in queries]
    report = build_report(
        db_path=db_path,
        local_model=args.local_model,
        candidate_model=args.candidate_model,
        counts=counts,
        common_count=len(chunks),
        comparisons=comparisons,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    summary = {
        "database": str(db_path),
        "output": str(out_path),
        "local_model": args.local_model,
        "candidate_model": args.candidate_model,
        "common_chunks": len(chunks),
        "queries": len(comparisons),
        "compared_queries": sum(1 for item in comparisons if item["status"] == "compared"),
        "skipped_queries": sum(1 for item in comparisons if item["status"] != "compared"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.json:
        print(json.dumps(comparisons, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
