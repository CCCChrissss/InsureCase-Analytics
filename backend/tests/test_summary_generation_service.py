from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import httpx
import pytest

from backend.app.services.summary_generation_service import FINAL_SUMMARY_SCHEMA
from backend.app.services.summary_generation_service import SECTION_EXTRACTION_SCHEMA
from backend.app.services.summary_generation_service import OllamaLocalSummaryProvider
from backend.app.services.summary_generation_service import SourcePacket
from backend.app.services.summary_generation_service import StructuredGeneration
from backend.app.services.summary_generation_service import SummaryGenerationError
from backend.app.services.summary_generation_service import _is_supported_quote
from backend.app.services.summary_generation_service import _deduplicate_statements
from backend.app.services.summary_generation_service import _extract_statutory_references
from backend.app.services.summary_generation_service import _validated_legal_reference
from backend.app.services.summary_generation_service import _is_table_like_statement
from backend.app.services.summary_generation_service import _has_complete_statement_ending
from backend.app.services.summary_generation_service import _has_balanced_quote_marks
from backend.app.services.summary_generation_service import _expand_quote_to_sentence
from backend.app.services.summary_generation_service import _extract_reasoning_signal_statements
from backend.app.services.summary_generation_service import _ranked_grounded_items
from backend.app.services.summary_generation_service import _grounded_item
from backend.app.services.summary_generation_service import _summary_display_text
from backend.app.services.summary_generation_service import _best_applicant_fallback_sentence
from backend.app.services.summary_generation_service import _best_respondent_fallback_sentence
from backend.app.services.summary_generation_service import _canonical_law_name
from backend.app.services.summary_generation_service import _display_texts_overlap
from backend.app.services.summary_generation_service import _ensure_high_signal_party_position
from backend.app.services.summary_generation_service import _remove_redundant_applicant_background
from backend.app.services.summary_generation_service import _source_fallback_statement
from backend.app.services.summary_generation_service import build_source_packets
from backend.app.services.summary_generation_service import generate_case_summary
from backend.app.services.summary_generation_service import split_text_exact
from backend.scripts.run_summary_trial import connect_read_only
from backend.scripts.run_summary_trial import select_representative_case_ids
from backend.scripts.validate_summary_trial import _is_source_grounded_law_name


def test_local_provider_rejects_remote_url_and_cloud_model() -> None:
    with pytest.raises(SummaryGenerationError, match="local HTTP"):
        OllamaLocalSummaryProvider(base_url="https://api.example.com", model_name="qwen3:4b")
    with pytest.raises(SummaryGenerationError, match="Cloud Ollama models are disabled"):
        OllamaLocalSummaryProvider(base_url="http://127.0.0.1:11434", model_name="qwen3:cloud")


def test_ollama_provider_uses_local_structured_output_without_auth_header() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3:4b"}]})
        return httpx.Response(
            200,
            json={
                "message": {"content": json.dumps({"statements": [], "legal_references": []})},
                "prompt_eval_count": 10,
                "eval_count": 4,
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaLocalSummaryProvider(client=client)

    inventory = provider.ensure_model_available()
    response = provider.generate_structured(
        system_prompt="system",
        user_prompt="user",
        schema=SECTION_EXTRACTION_SCHEMA,
    )

    assert inventory["model"] == "qwen3:4b"
    assert response.content == {"statements": [], "legal_references": []}
    request = requests[-1]
    payload = json.loads(request.content)
    assert request.url == httpx.URL("http://127.0.0.1:11434/api/chat")
    assert "authorization" not in request.headers
    assert payload["model"] == "qwen3:4b"
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["format"] == SECTION_EXTRACTION_SCHEMA
    assert payload["options"]["num_predict"] == 2048


def test_split_text_exact_preserves_every_character() -> None:
    text = "第一段內容。\n第二段內容很長。\n第三段結尾。"

    parts = split_text_exact(text, max_chars=12)

    assert "".join(part[2] for part in parts) == text
    assert all(len(part[2]) <= 12 for part in parts)


def test_split_text_does_not_treat_pdf_line_wrap_as_sentence_boundary() -> None:
    text = "第一句已結束。\n第二句仍在繼續但\n尚未結束。第三句。"

    parts = split_text_exact(text, max_chars=18)

    assert parts[0][2] == "第一句已結束。"
    assert "".join(part[2] for part in parts) == text


def test_evidence_check_ignores_page_markers_and_model_quote_wrappers() -> None:
    source = "第一項保險契約應繳保險費及\n-第2頁，共3頁-\n--- page 3 ---\n其他費用後恢復效力。"
    model_quote = "「第一項保險契約應繳保險費及其他費用後恢復效力。…」"

    assert _is_supported_quote(model_quote, source) is True


def test_short_issue_section_has_traceable_source_fallback() -> None:
    packet = SourcePacket(
        section_id="issues_1",
        section_type="issues",
        title="本件爭點",
        part_index=1,
        start_offset=100,
        end_offset=122,
        text="本件爭點：申請人之請求有無理由？",
    )

    statement = _source_fallback_statement(packet=packet, statement_id="statement_0001")

    assert statement is not None
    assert statement["category"] == "core_issue"
    assert statement["source_fallback"] is True
    assert statement["evidence_quote"] == "本件爭點：申請人之請求有無理由？"


def test_long_party_section_fallback_ends_at_a_complete_sentence() -> None:
    packet = SourcePacket(
        section_id="respondent_claim_1",
        section_type="respondent_claim",
        title="相對人主張",
        part_index=1,
        start_offset=0,
        end_offset=400,
        text="相對人主張：" + "甲" * 150 + "。" + "乙" * 240,
    )

    statement = _source_fallback_statement(packet=packet, statement_id="statement_0001")

    assert statement is not None
    assert statement["category"] == "respondent_position"
    assert statement["text"].endswith("。")
    assert len(statement["text"]) <= 300


def test_long_party_section_fallback_stops_before_unclosed_quote() -> None:
    packet = SourcePacket(
        section_id="respondent_claim_1",
        section_type="respondent_claim",
        title="相對人主張",
        part_index=1,
        start_offset=0,
        end_offset=500,
        text="三、相對人之主張：申請人之請求為無理由。相對人引用：「" + "契約內容" * 80 + "。後續內容」",
    )

    statement = _source_fallback_statement(packet=packet, statement_id="statement_0001")

    assert statement is not None
    assert statement["text"] == "三、相對人之主張：申請人之請求為無理由。"
    assert "「" not in statement["text"]


def test_respondent_fallback_prefers_complete_case_specific_rationale() -> None:
    source = (
        "三、相對人之主張：申請人之請求為無理由。"
        "相對人引用：「契約約定內容。」"
        "(3)查申請人後續多次繳息，應視為已承認債務，故其請求無理由。"
    )

    selected = _best_respondent_fallback_sentence(source)

    assert selected == "(3)查申請人後續多次繳息，應視為已承認債務，故其請求無理由。"
    assert selected in source


def test_respondent_fallback_splits_quote_closed_after_ellipsis() -> None:
    source = (
        "三、相對人之主張：申請人之請求為無理由。"
        "病歷記載：「申請人投保前已有相關症狀…」"
        "申請人投保前曾接受手術，是以相對人歉難依其主張辦理。"
    )

    selected = _best_respondent_fallback_sentence(source)

    assert selected == "申請人投保前曾接受手術，是以相對人歉難依其主張辦理。"


def test_table_density_filter_rejects_numeric_rows_but_keeps_prose() -> None:
    assert _is_table_like_statement("貸款償還97/12/26900,594893,0007,594") is True
    assert _is_table_like_statement("申請人請求返還超收利息232,813元，並主張約定利率不明。") is False


def test_statement_quote_must_end_at_a_sentence_boundary() -> None:
    assert _has_complete_statement_ending("本中心認為請求無理由。") is True
    # Some source decisions use an ASCII question mark after Chinese text.
    assert _has_complete_statement_ending("申請人的請求是否有據?") is True
    assert _has_complete_statement_ending("本中心認為請求無理") is False


def test_applicant_fallback_prefers_request_over_policy_history() -> None:
    source = (
        "申請人於109年間向相對人投保系爭保險契約。"
        "請求標的：相對人應給付醫療保險金45,800元及利息。"
        "申請人後續接受治療並提出理賠申請。"
    )

    selected = _best_applicant_fallback_sentence(source)

    assert selected == "請求標的：相對人應給付醫療保險金45,800元及利息。"


def test_low_information_party_choice_is_replaced_by_rule_based_supplement() -> None:
    statement_map = {
        "history": {
            "category": "respondent_position",
            "section_type": "respondent_claim",
            "text": "相對人於收到申請後調閱相關資料。",
        },
        "defence": {
            "category": "respondent_position",
            "section_type": "respondent_claim",
            "text": "病歷未見外傷紀錄，因此相對人主張不符合意外事故要件。",
            "rule_based_party_position": True,
        },
    }

    item = _ensure_high_signal_party_position(
        {"text": statement_map["history"]["text"], "statement_ids": ["history"]},
        category="respondent_position",
        statement_map=statement_map,
    )

    assert item == {
        "text": "病歷未見外傷紀錄，因此相對人主張不符合意外事故要件。",
        "statement_ids": ["defence"],
    }


def test_statement_quote_marks_must_be_balanced() -> None:
    assert _has_balanced_quote_marks("相對人引用：「完整條文。」") is True
    assert _has_balanced_quote_marks("相對人引用：「尚未結束。") is False


def test_quote_fragment_expands_to_exact_source_sentence() -> None:
    source = "前段規則。經查相對人已給付，足認請求標的已獲滿足。後段結論。"

    expanded = _expand_quote_to_sentence("相對人已給付，足認請求標的", source)

    assert expanded == "經查相對人已給付，足認請求標的已獲滿足。"


def test_quote_expansion_removes_prior_statutory_quote_tail() -> None:
    source = (
        "又依保險法規定：「清償保險費後恢復效力。…」"
        "而相對人既已同意保單復效，申請人仍應繳清保險費，併予敘明。"
    )

    expanded = _expand_quote_to_sentence("而相對人既已同意保單復效", source)

    assert expanded == "而相對人既已同意保單復效，申請人仍應繳清保險費，併予敘明。"
    assert expanded in source


def test_quote_expansion_preserves_ellipsis_inside_reasoning() -> None:
    source = "經查申請人所述…尚無其他證據可佐，難認其請求有據。"

    expanded = _expand_quote_to_sentence("申請人所述…尚無其他證據可佐", source)

    assert expanded == source


@pytest.mark.parametrize(
    ("section_type", "source_text", "expected"),
    [
        ("holding", "主文本中心就申請人之請求尚難為有利之認定。", "本中心就申請人之請求尚難為有利之認定。"),
        ("undisputed_facts", "四、兩造不爭執之事實：相對人同意恢復保單效力。", "相對人同意恢復保單效力。"),
        ("undisputed_facts", "(二)保單於投保後曾辦理借款。", "保單於投保後曾辦理借款。"),
        ("issues", "五、本件爭點：申請人請求恢復保單效力，是否有據？", "申請人請求恢復保單效力，是否有據？"),
        ("respondent_claim", "(二)陳述：相對人已同意恢復保單效力。", "相對人已同意恢復保單效力。"),
        ("applicant_claim", "二、申請人之主張：(一)請求標的：1.請求返還利息。", "請求返還利息。"),
        (
            "applicant_claim",
            "請求返還利息。2.請求懲罰性賠償。(二)陳述：1.相對人以保單借款方式收取利息。",
            "請求返還利息。 請求懲罰性賠償。 相對人以保單借款方式收取利息。",
        ),
        (
            "issues",
            "(一)借款是否約定利率？(二)懲罰性賠償是否有據？",
            "借款是否約定利率？ 懲罰性賠償是否有據？",
        ),
        ("reasoning", "3.由上可知，雙方已約定借款利率。", "由上可知，雙方已約定借款利率。"),
        ("conclusion", "七、綜上所述，本中心尚難為有利之認定。", "本中心尚難為有利之認定。"),
        (
            "conclusion",
            "七、綜上所述，本中心尚難為有利之認定。兩造其餘陳述及攻擊防禦方法，經審酌與結果不生影響，爰不一一論述，併予敘明。",
            "本中心尚難為有利之認定。",
        ),
        ("respondent_claim", "(3)申請人已承認全部債務，故其請求無理由。", "申請人已承認全部債務，故其請求無理由。"),
        ("disposition", "八、據上論結，本件評議申請為無理由。", "本件評議申請為無理由。"),
    ],
)
def test_summary_display_removes_only_known_section_prefixes(
    section_type: str,
    source_text: str,
    expected: str,
) -> None:
    statement = {"text": source_text, "section_type": section_type}

    assert _summary_display_text(statement) == expected
    assert statement["text"] == source_text


def test_grounded_item_cleans_display_text_but_preserves_evidence() -> None:
    source_text = "八、據上論結，本件評議申請為無理由。"
    statement_map = {
        "statement_0001": {
            "category": "decision_result",
            "section_type": "disposition",
            "text": source_text,
            "evidence_quote": source_text,
        }
    }

    item = _grounded_item(
        {"statement_ids": ["statement_0001"]},
        statement_map,
        allowed_categories={"decision_result"},
    )

    assert item["text"] == "本件評議申請為無理由。"
    assert statement_map["statement_0001"]["evidence_quote"] == source_text


def test_grounded_item_orders_conclusion_before_disposition() -> None:
    statement_map = {
        "holding": {
            "category": "decision_result",
            "section_type": "holding",
            "text": "主文本中心尚難為有利之認定。",
        },
        "disposition": {
            "category": "decision_result",
            "section_type": "disposition",
            "text": "八、據上論結，本件評議申請為無理由。",
        },
        "conclusion": {
            "category": "decision_result",
            "section_type": "conclusion",
            "text": "七、綜上所述，本中心尚難為有利之認定。",
        },
    }

    item = _grounded_item(
        {"statement_ids": ["holding", "disposition", "conclusion"]},
        statement_map,
        allowed_categories={"decision_result"},
        max_statement_count=2,
        preferred_section_types=("holding", "conclusion", "disposition"),
    )

    assert item["text"] == "本中心尚難為有利之認定。 本件評議申請為無理由。"


def test_display_text_overlap_merges_trivial_wording_variants_only() -> None:
    assert _display_texts_overlap(
        "本中心就申請人之請求尚難為有利於申請人之認定。",
        "本中心就申請人之請求尚難為有利申請人之認定。",
    ) is True
    assert _display_texts_overlap(
        "相對人應給付申請人新臺幣一萬元。",
        "申請人逾一萬元之請求為無理由。",
    ) is False


def test_display_text_overlap_merges_same_negative_holding_with_different_object() -> None:
    assert _display_texts_overlap(
        "本中心就申請人之請求尚難為有利申請人之認定。",
        "申請人請求相對人給付系爭保險金，本中心尚難為有利申請人之認定。",
    ) is True


def test_display_text_overlap_ignores_punctuation_for_contained_decision() -> None:
    assert _display_texts_overlap(
        "申請人請求解除房屋買賣契約之部分，不受理。",
        "申請人請求解除房屋買賣契約之部分不受理；申請人其餘請求為無理由。",
    ) is True


def test_respondent_display_text_removes_leading_continuation_marks() -> None:
    assert _summary_display_text(
        {
            "section_type": "respondent_claim",
            "text": "，經檢視病歷，未見立即手術之必要。",
        }
    ) == "經檢視病歷，未見立即手術之必要。"
    assert _summary_display_text(
        {
            "section_type": "respondent_claim",
            "text": "而相對人諮詢醫療顧問後，認為不符給付要件。",
        }
    ) == "相對人諮詢醫療顧問後，認為不符給付要件。"


def test_applicant_position_drops_policy_history_already_shown_in_background() -> None:
    statement_map = {
        "claim": {
            "category": "applicant_position",
            "section_type": "applicant_claim",
            "text": "申請人主張相對人拒絕理賠並無理由。",
        },
        "policy_history": {
            "category": "applicant_position",
            "section_type": "applicant_claim",
            "text": "申請人於108年9月23日向相對人投保保險契約，並附加醫療附約。",
        },
    }

    item = _remove_redundant_applicant_background(
        {
            "text": "申請人主張相對人拒絕理賠並無理由。 申請人於108年9月23日向相對人投保保險契約，並附加醫療附約。",
            "statement_ids": ["claim", "policy_history"],
        },
        background_text="申請人於108年9月23日投保系爭保險契約。",
        statement_map=statement_map,
    )

    assert item == {
        "text": "申請人主張相對人拒絕理賠並無理由。",
        "statement_ids": ["claim"],
    }


def test_applicant_position_keeps_only_available_policy_history() -> None:
    statement_map = {
        "policy_history": {
            "category": "applicant_position",
            "section_type": "applicant_claim",
            "text": "申請人於108年9月23日向相對人投保保險契約，並附加醫療附約。",
        }
    }
    original = {
        "text": "申請人於108年9月23日向相對人投保保險契約，並附加醫療附約。",
        "statement_ids": ["policy_history"],
    }

    assert _remove_redundant_applicant_background(
        original,
        background_text="申請人於108年9月23日投保系爭保險契約。",
        statement_map=statement_map,
    ) == original


def test_ranked_reasoning_excludes_issue_restatement_when_reason_exists() -> None:
    statement_map = {
        "reason": {
            "category": "reasoning",
            "section_type": "reasoning",
            "text": "是以，依現有資料可知治療不符一般醫療常規，請求難謂有據。",
        },
        "issue_restatement": {
            "category": "reasoning",
            "section_type": "reasoning",
            "text": "準此，本件爭點厥為：申請人接受手術有無醫療必要性？",
        },
    }

    items = _ranked_grounded_items(
        statement_map,
        allowed_categories={"reasoning"},
        max_items=3,
    )

    assert [item["statement_ids"] for item in items] == [["reason"]]


def test_ranked_reasoning_excludes_issue_restatement_using_should_be_wording() -> None:
    statement_map = {
        "reason": {
            "category": "reasoning",
            "section_type": "reasoning",
            "text": "經查病歷未見必要性，故申請人的請求無理由。",
        },
        "issue_restatement": {
            "category": "reasoning",
            "section_type": "reasoning",
            "text": "是本件爭點應為申請人的治療是否有必要性？",
        },
    }

    items = _ranked_grounded_items(
        statement_map,
        allowed_categories={"reasoning"},
        max_items=3,
    )

    assert [item["statement_ids"] for item in items] == [["reason"]]


def test_rule_based_reasoning_keeps_complete_case_application_sentence() -> None:
    document = {
        "sections": [
            {
                "section_id": "reasoning_1",
                "section_type": "reasoning",
                "title": "判斷理由",
                "start_offset": 100,
                "end_offset": 180,
                "content": (
                    "按民法規定：「內部引文。尚未結束」。"
                    "既相對人已給付，從而難認申請人之請求有據。"
                ),
            }
        ]
    }

    statements = _extract_reasoning_signal_statements(document)

    assert [item["text"] for item in statements] == ["既相對人已給付，從而難認申請人之請求有據。"]
    assert statements[0]["rule_based_reasoning"] is True


def test_rule_based_reasoning_keeps_partial_award_basis_from_long_paragraph() -> None:
    award_basis = (
        "衡酌本件事實情狀及證據取捨，爰依金融消費者保護法第20條第1項所揭示之公平合理原則，"
        "認相對人除已給付部分外，應仍有補償申請人之必要，其補償金額以一萬元為適當。"
    )
    document = {
        "sections": [
            {
                "section_id": "reasoning_1",
                "section_type": "reasoning",
                "title": "判斷理由",
                "start_offset": 100,
                "end_offset": 600,
                # The prefix makes the full paragraph exceed the generic
                # sentence limit while the decision-driving clause stays short.
                "content": "相對人理賠程序之說明" + "甲" * 350 + "，" + award_basis,
            }
        ]
    }

    statements = _extract_reasoning_signal_statements(document)

    assert any(statement["text"] == award_basis for statement in statements)
    assert any(statement["reasoning_signal_score"] == 30 for statement in statements)


def test_rule_based_reasoning_expands_context_for_collective_unknown_conclusion() -> None:
    document = {
        "sections": [
            {
                "section_id": "reasoning_1",
                "section_type": "reasoning",
                "title": "判斷理由",
                "start_offset": 0,
                "end_offset": 100,
                "content": (
                    "前段說明。申請人何時收到款項？當時匯率為何？是否實際受有損害？"
                    "均無法確認，是依現有事證，本中心尚難認定申請人之請求有據。"
                ),
            }
        ]
    }

    statements = _extract_reasoning_signal_statements(document)

    assert statements[0]["text"] == (
        "申請人何時收到款項？當時匯率為何？是否實際受有損害？"
        "均無法確認，是依現有事證，本中心尚難認定申請人之請求有據。"
    )


def test_statement_deduplication_keeps_longer_overlapping_quote() -> None:
    statements = [
        {"category": "applicant_position", "evidence_quote": "申請人主張無疾病。", "text": "短句"},
        {
            "category": "applicant_position",
            "evidence_quote": "申請人提出檢查報告，並主張投保前無疾病。",
            "text": "不同句",
        },
        {
            "category": "applicant_position",
            "evidence_quote": "申請人提出檢查報告，並主張投保前無疾病。爰提起評議。",
            "text": "完整句",
        },
    ]

    deduplicated = _deduplicate_statements(statements)

    assert [item["text"] for item in deduplicated] == ["短句", "完整句"]


def test_reasoning_selection_prioritizes_case_application_over_contract_quote() -> None:
    statement_map = {
        "statement_0001": {
            "category": "reasoning",
            "text": "按保單契約條款第十條約定辦理。",
        },
        "statement_0002": {
            "category": "reasoning",
            "text": "經查相對人已給付，足認申請人之請求標的已獲滿足。",
        },
    }

    selected = _ranked_grounded_items(
        statement_map,
        allowed_categories={"reasoning"},
        max_items=1,
    )

    assert selected == [
        {
            "text": "經查相對人已給付，足認申請人之請求標的已獲滿足。",
            "statement_ids": ["statement_0002"],
        }
    ]


def test_rule_based_statutory_reference_extraction_keeps_laws_only() -> None:
    packet = SourcePacket(
        section_id="reasoning_1",
        section_type="reasoning",
        title="判斷理由",
        part_index=1,
        start_offset=0,
        end_offset=70,
        text="又依保險法第 116 條第 3 項規定辦理；保單契約條款第十條不屬法源。",
    )

    references = _extract_statutory_references(packet)

    assert references == [
        {
            "law_name": "保險法",
            "article": "第116條第3項",
            "section_id": "reasoning_1",
            "section_title": "判斷理由",
            "evidence_quote": "又依保險法第116條第3項",
            "extraction_source": "rule_based",
        }
    ]


def test_statutory_reference_uses_law_nearest_article_in_long_context() -> None:
    packet = SourcePacket(
        section_id="reasoning_1",
        section_type="reasoning",
        title="判斷理由",
        part_index=1,
        start_offset=0,
        end_offset=80,
        text="依保險法相關規定從事擔保及保證放款涉屬銀行法第12條規範。",
    )

    references = _extract_statutory_references(packet)

    assert references[0]["law_name"] == "銀行法"
    assert references[0]["article"] == "第12條"
    assert _canonical_law_name("保險法相關規定從事擔保及保證放款涉屬銀行法") == "銀行法"


def test_statutory_reference_keeps_article_suffix_and_expands_common_alias() -> None:
    packet = SourcePacket(
        section_id="reasoning_1",
        section_type="reasoning",
        title="判斷理由",
        part_index=1,
        start_offset=0,
        end_offset=80,
        text="按保險法第54條之1規定審酌，爰依金保法第27條第2項決定。",
    )

    references = _extract_statutory_references(packet)

    assert [(item["law_name"], item["article"]) for item in references] == [
        ("保險法", "第54條之1"),
        ("金融消費者保護法", "第27條第2項"),
    ]
    assert _is_source_grounded_law_name("金融消費者保護法", packet.text) is True


def test_party_statutory_references_are_not_presented_as_panel_legal_bases() -> None:
    packet = SourcePacket(
        section_id="applicant_claim_1",
        section_type="applicant_claim",
        title="申請人主張",
        part_index=1,
        start_offset=0,
        end_offset=30,
        text="申請人主張依民法第203條請求返還利息。",
    )
    raw_reference = {
        "law_name": "民法",
        "article": "第203條",
        "evidence_quote": "依民法第203條",
    }

    assert _validated_legal_reference(raw_reference, packet=packet) is None
    assert _extract_statutory_references(packet) == []


def test_build_source_packets_skips_notice_but_keeps_relevant_offsets() -> None:
    structured_document = {
        "sections": [
            {
                "section_id": "applicant_claim_1",
                "section_type": "applicant_claim",
                "title": "申請人主張",
                "content": "申請人請求給付保險金。",
                "start_offset": 20,
            },
            {
                "section_id": "notice_2",
                "section_type": "notice",
                "title": "附註",
                "content": "權利說明。",
                "start_offset": 33,
            },
        ]
    }

    packets = build_source_packets(structured_document, max_chars=100)

    assert len(packets) == 1
    assert packets[0].section_id == "applicant_claim_1"
    assert packets[0].start_offset == 20
    assert packets[0].end_offset == 31


class FakeSummaryProvider:
    provider_name = "fake_local"
    model_name = "fake_model"

    def __init__(self) -> None:
        self.section_call_count = 0

    def ensure_model_available(self) -> dict:
        return {}

    def generate_structured(self, *, system_prompt: str, user_prompt: str, schema: dict) -> StructuredGeneration:
        if schema == SECTION_EXTRACTION_SCHEMA:
            self.section_call_count += 1
            if "申請人主張" in user_prompt:
                content = {
                    "statements": [
                        {
                            # The parser-owned section type must correct this model role error.
                            "category": "reasoning",
                            # The unsupported paraphrase must be replaced by its source quote.
                            "text": "申請人已經獲得住院保險金。",
                            "evidence_quote": "「申請人請求給付住院保險金。…」",
                        },
                        {
                            "category": "background",
                            "text": "這是原文沒有的內容。",
                            "evidence_quote": "不存在的證據",
                        },
                    ],
                    "legal_references": [],
                }
            else:
                content = {
                    "statements": [
                        {
                            # A respondent claim cannot become neutral background.
                            "category": "background",
                            "text": "相對人主張不符合住院定義。",
                            "evidence_quote": "相對人主張不符合住院定義。",
                        }
                    ],
                    "legal_references": [
                        {
                            "law_name": "住院醫療保險契約條款",
                            "article": "第十條",
                            "evidence_quote": "住院醫療保險契約條款第十條",
                        }
                    ],
                }
            return StructuredGeneration(content=content, metrics={"elapsed_ms": 1.0})

        assert schema == FINAL_SUMMARY_SCHEMA
        return StructuredGeneration(
            content={
                "background": {"text": "", "statement_ids": []},
                "applicant_position": {
                    "text": "模型不可新增的申請人說法。",
                    "statement_ids": ["statement_0001"],
                },
                "respondent_position": {
                    "text": "模型不可新增的相對人說法。",
                    "statement_ids": ["statement_0002"],
                },
                "core_issues": [],
                "reasoning_points": [
                    {"text": "不得把申請人主張誤作判斷理由。", "statement_ids": ["statement_0001"]}
                ],
                "decision_result": {"text": "", "statement_ids": []},
            },
            metrics={"elapsed_ms": 1.0},
        )


class PartiallyFailingSummaryProvider(FakeSummaryProvider):
    """Simulate one local generation failure while later packets still succeed."""

    def generate_structured(self, *, system_prompt: str, user_prompt: str, schema: dict) -> StructuredGeneration:
        if schema == SECTION_EXTRACTION_SCHEMA and "申請人主張" in user_prompt:
            raise SummaryGenerationError("simulated local timeout")
        return super().generate_structured(system_prompt=system_prompt, user_prompt=user_prompt, schema=schema)


def test_generate_case_summary_keeps_only_source_grounded_content() -> None:
    structured_document = {
        "sections": [
            {
                "section_id": "applicant_claim_1",
                "section_type": "applicant_claim",
                "title": "申請人主張",
                "content": "申請人主張：申請人請求給付住院保險金。",
                "start_offset": 0,
            },
            {
                "section_id": "respondent_claim_2",
                "section_type": "respondent_claim",
                "title": "相對人主張",
                "content": "相對人主張不符合住院定義。住院醫療保險契約條款第十條。",
                "start_offset": 24,
            },
        ]
    }

    result = generate_case_summary(
        case_metadata={"case_id": "case_1", "case_number": "115年評字第1號"},
        structured_document=structured_document,
        provider=FakeSummaryProvider(),
        max_section_chars=1000,
    )

    summary = result["summary"]
    assert summary["applicant_position"] == "申請人請求給付住院保險金。"
    assert summary["respondent_position"] == "相對人主張不符合住院定義。"
    assert summary["reasoning_points"] == []
    assert summary["legal_references"] == []
    assert len(summary["evidence"]) == 2
    # Display cleanup must not alter the verbatim statement retained for audit.
    assert summary["evidence"][0]["evidence_quote"] == "申請人主張：申請人請求給付住院保險金。"
    assert result["generation"]["validated_statement_count"] == 2
    assert result["generation"]["corrected_category_count"] == 2
    assert result["generation"]["extractive_fallback_count"] == 1
    assert result["generation"]["rejected_statement_count"] == 1
    assert result["generation"]["rejected_legal_reference_count"] == 1
    assert result["generation"]["review_status"] == "unreviewed"


def test_case_summary_keeps_partial_result_when_one_packet_fails() -> None:
    structured_document = {
        "sections": [
            {
                "section_id": "applicant_claim_1",
                "section_type": "applicant_claim",
                "title": "申請人主張",
                "content": "申請人主張：申請人請求給付住院保險金。",
                "start_offset": 0,
            },
            {
                "section_id": "respondent_claim_2",
                "section_type": "respondent_claim",
                "title": "相對人主張",
                "content": "相對人主張不符合住院定義。",
                "start_offset": 24,
            },
        ]
    }

    result = generate_case_summary(
        case_metadata={"case_id": "case_1", "case_number": "115年評字第1號"},
        structured_document=structured_document,
        provider=PartiallyFailingSummaryProvider(),
        max_section_chars=1000,
    )

    assert result["summary"]["applicant_position"] == "申請人請求給付住院保險金。"
    assert result["summary"]["respondent_position"] == "相對人主張不符合住院定義。"
    assert result["summary"]["evidence"][0]["evidence_quote"] == "申請人主張：申請人請求給付住院保險金。"
    assert result["generation"]["attempted_request_count"] == 3
    assert result["generation"]["failed_request_count"] == 1
    assert result["generation"]["request_errors"][0]["section_type"] == "applicant_claim"


def test_summary_trial_database_connection_is_read_only(tmp_path: Path) -> None:
    db_path = tmp_path / "cases.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE sample (value TEXT);")
        connection.execute("INSERT INTO sample VALUES ('unchanged');")

    with connect_read_only(db_path) as connection:
        assert connection.execute("SELECT value FROM sample;").fetchone()[0] == "unchanged"
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("INSERT INTO sample VALUES ('must fail');")


def test_representative_selection_prefers_different_dispute_types(tmp_path: Path) -> None:
    db_path = tmp_path / "cases.db"
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE cases (
              case_id TEXT PRIMARY KEY,
              case_number TEXT NOT NULL,
              dispute_type TEXT,
              decision_result TEXT
            );
            CREATE TABLE case_texts (
              case_id TEXT PRIMARY KEY,
              normalized_text TEXT,
              normalized_text_chars INTEGER
            );
            """
        )
        for index, dispute_type in enumerate(("類型甲", "類型甲", "類型乙", "類型丙", "類型丁"), start=1):
            case_id = f"case_{index}"
            connection.execute(
                "INSERT INTO cases VALUES (?, ?, ?, '全部');",
                (case_id, f"115年評字第{index:06d}號", dispute_type),
            )
            connection.execute(
                "INSERT INTO case_texts VALUES (?, ?, ?);",
                (case_id, "測" * (1000 + index * 100), 1000 + index * 100),
            )

        selected = select_representative_case_ids(connection, limit=3)
        placeholders = ",".join("?" for _ in selected)
        selected_types = {
            row[0]
            for row in connection.execute(
                f"SELECT dispute_type FROM cases WHERE case_id IN ({placeholders});",
                selected,
            )
        }

    assert len(selected) == 3
    assert len(selected_types) == 3
