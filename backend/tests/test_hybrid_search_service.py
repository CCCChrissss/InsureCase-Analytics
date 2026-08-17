from __future__ import annotations

from backend.app.services import embedding_service
from backend.app.services import hybrid_search_service


def semantic_result(*case_ids: str) -> dict:
    """Build deterministic full-database semantic rankings without loading AI."""
    return {
        "query": "住院後遭拒賠",
        "embedding_provider": "fake",
        "embedding_model": "fake_model",
        "embedding_dims": 3,
        "embedding_device": "cpu",
        "elapsed_ms": 1.0,
        "total_cases": len(case_ids),
        "total_candidates": len(case_ids),
        "items": [
            {
                "case_id": case_id,
                "case_number": f"115年評字第{index:06d}號",
                "decision_date": f"115.01.{index:02d}",
                "dispute_type": "必要性醫療",
                "decision_result": None,
                "holding": "本中心就申請人之請求尚難為有利之認定。",
                "similarity_score": round(0.95 - index * 0.05, 4),
                "section_hint": "判斷理由",
                "chunk_index": index,
                "semantic_snippet": f"{case_id} 的語意命中原文",
            }
            for index, case_id in enumerate(case_ids, start=1)
        ],
    }


def keyword_result(*case_ids: str) -> dict:
    """Build the stable shape returned by search_all_cases."""
    return {
        "query": "住院後遭拒賠",
        "total": len(case_ids),
        "match_source": "fts5",
        "items": [
            {
                "case_id": case_id,
                "case_number": f"115年評字第{index:06d}號",
                "decision_date": f"115.01.{index:02d}",
                "dispute_type": "必要性醫療",
                "decision_result": "無理由",
                "snippet": f"{case_id} 的文字命中原文",
                "match_source": "fts5",
            }
            for index, case_id in enumerate(case_ids, start=1)
        ],
    }


def configure_cache_key(monkeypatch) -> None:
    monkeypatch.setattr(
        hybrid_search_service.embedding_service,
        "semantic_ranked_database_key",
        lambda: ("test.db", 1, 1),
    )
    hybrid_search_service.clear_hybrid_search_cache()


def test_hybrid_search_includes_semantic_case_without_literal_match(monkeypatch) -> None:
    configure_cache_key(monkeypatch)
    monkeypatch.setattr(hybrid_search_service, "search_all_cases", lambda _: keyword_result())
    monkeypatch.setattr(
        hybrid_search_service.embedding_service,
        "semantic_case_rankings",
        lambda *args, **kwargs: semantic_result("semantic_only", "another_case"),
    )

    result = hybrid_search_service.hybrid_search(
        "住院後遭拒賠",
        page=1,
        page_size=10,
        provider_name="fake",
        model_name="fake_model",
    )

    assert result["search_mode"] == "hybrid"
    assert result["keyword_match_count"] == 0
    assert result["total"] == 2
    assert result["items"][0]["case_id"] == "semantic_only"
    assert result["items"][0]["match_type"] == "semantic"
    assert result["items"][0]["snippet"] == "semantic_only 的語意命中原文"


def test_hybrid_search_fuses_keyword_and_semantic_ranks(monkeypatch) -> None:
    configure_cache_key(monkeypatch)
    monkeypatch.setattr(hybrid_search_service, "search_all_cases", lambda _: keyword_result("both"))
    monkeypatch.setattr(
        hybrid_search_service.embedding_service,
        "semantic_case_rankings",
        lambda *args, **kwargs: semantic_result("semantic_first", "both"),
    )

    result = hybrid_search_service.hybrid_search(
        "住院後遭拒賠",
        provider_name="fake",
        model_name="fake_model",
    )

    # The exact text signal supplements semantic ranking instead of gating it.
    assert result["items"][0]["case_id"] == "both"
    assert result["items"][0]["match_type"] == "hybrid"
    assert result["items"][0]["keyword_rank"] == 1
    assert result["items"][0]["semantic_rank"] == 2
    assert {item["case_id"] for item in result["items"]} == {"semantic_first", "both"}


def test_hybrid_search_falls_back_to_keyword_when_embedding_is_unavailable(monkeypatch) -> None:
    configure_cache_key(monkeypatch)
    monkeypatch.setattr(hybrid_search_service, "search_all_cases", lambda _: keyword_result("keyword_only"))

    def fail_semantic(*args, **kwargs):
        raise embedding_service.EmbeddingProviderError("local model unavailable")

    monkeypatch.setattr(hybrid_search_service.embedding_service, "semantic_case_rankings", fail_semantic)

    result = hybrid_search_service.hybrid_search(
        "住院後遭拒賠",
        provider_name="fake",
        model_name="fake_model",
    )

    assert result["search_mode"] == "keyword_fallback"
    assert result["fallback_reason"] == "local model unavailable"
    assert result["items"][0]["case_id"] == "keyword_only"
    assert result["items"][0]["similarity_score"] is None


def test_hybrid_search_caches_complete_ranking_before_pagination(monkeypatch) -> None:
    configure_cache_key(monkeypatch)
    calls = 0
    monkeypatch.setattr(hybrid_search_service, "search_all_cases", lambda _: keyword_result())

    def ranked(*args, **kwargs):
        nonlocal calls
        calls += 1
        return semantic_result("case_1", "case_2")

    monkeypatch.setattr(hybrid_search_service.embedding_service, "semantic_case_rankings", ranked)

    first = hybrid_search_service.hybrid_search(
        "住院後遭拒賠",
        page=1,
        page_size=1,
        provider_name="fake",
        model_name="fake_model",
    )
    second = hybrid_search_service.hybrid_search(
        "住院後遭拒賠",
        page=2,
        page_size=1,
        provider_name="fake",
        model_name="fake_model",
    )

    assert calls == 1
    assert first["cached"] is False
    assert first["items"][0]["case_id"] == "case_1"
    assert second["cached"] is True
    assert second["items"][0]["case_id"] == "case_2"
