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
from backend.app.services.summary_generation_service import _is_table_like_statement
from backend.app.services.summary_generation_service import _has_complete_statement_ending
from backend.app.services.summary_generation_service import _expand_quote_to_sentence
from backend.app.services.summary_generation_service import _extract_reasoning_signal_statements
from backend.app.services.summary_generation_service import _ranked_grounded_items
from backend.app.services.summary_generation_service import _grounded_item
from backend.app.services.summary_generation_service import _summary_display_text
from backend.app.services.summary_generation_service import _source_fallback_statement
from backend.app.services.summary_generation_service import build_source_packets
from backend.app.services.summary_generation_service import generate_case_summary
from backend.app.services.summary_generation_service import split_text_exact
from backend.scripts.run_summary_trial import connect_read_only
from backend.scripts.run_summary_trial import select_representative_case_ids


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


def test_table_density_filter_rejects_numeric_rows_but_keeps_prose() -> None:
    assert _is_table_like_statement("貸款償還97/12/26900,594893,0007,594") is True
    assert _is_table_like_statement("申請人請求返還超收利息232,813元，並主張約定利率不明。") is False


def test_statement_quote_must_end_at_a_sentence_boundary() -> None:
    assert _has_complete_statement_ending("本中心認為請求無理由。") is True
    assert _has_complete_statement_ending("本中心認為請求無理") is False


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
        ("issues", "五、本件爭點：申請人請求恢復保單效力，是否有據？", "申請人請求恢復保單效力，是否有據？"),
        ("respondent_claim", "(二)陳述：相對人已同意恢復保單效力。", "相對人已同意恢復保單效力。"),
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
