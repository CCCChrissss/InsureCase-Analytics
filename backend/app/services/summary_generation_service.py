from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from backend.app.config import OLLAMA_BASE_URL
from backend.app.config import SUMMARY_MODEL
from backend.app.config import SUMMARY_MAX_OUTPUT_TOKENS
from backend.app.config import SUMMARY_NUM_CTX
from backend.app.config import SUMMARY_PROVIDER
from backend.app.config import SUMMARY_REQUEST_TIMEOUT_SECONDS
from backend.app.config import SUMMARY_SECTION_MAX_CHARS


PROMPT_VERSION = "local_llm_summary_v4"
OLLAMA_LOCAL_PROVIDER = "ollama_local"
ALLOWED_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
SUMMARY_CATEGORIES = {
    "background",
    "applicant_position",
    "respondent_position",
    "core_issue",
    "reasoning",
    "decision_result",
}
SUMMARY_SECTION_TYPES = {
    "holding",
    "applicant_claim",
    "respondent_claim",
    "undisputed_facts",
    "issues",
    "reasoning",
    "conclusion",
    "disposition",
}
# The deterministic parser is a stronger role signal than a small model's label.
# Constraining each section prevents a party's allegation from becoming panel reasoning.
SUMMARY_CATEGORY_BY_SECTION_TYPE = {
    "holding": "decision_result",
    "applicant_claim": "applicant_position",
    "respondent_claim": "respondent_position",
    "undisputed_facts": "background",
    "issues": "core_issue",
    "reasoning": "reasoning",
    "conclusion": "decision_result",
    "disposition": "decision_result",
}
LAW_NAME_RE = re.compile(r"(?:法|條例|規則|辦法|準則|要點)$")
ARTICLE_NUMBER_PATTERN = r"[一二三四五六七八九十百千零〇0-9之\-]+"
ARTICLE_RE = re.compile(rf"第{ARTICLE_NUMBER_PATTERN}條(?:第{ARTICLE_NUMBER_PATTERN}項)?")
POLICY_REFERENCE_RE = re.compile(r"保單|附約|契約條款|保險契約條款")
CONTRACT_QUOTE_RE = re.compile(r"(?:保單|附約).{0,20}條款|契約條款")
PAGE_ARTIFACT_RE = re.compile(r"-第\s*\d+\s*頁，共\s*\d+\s*頁-|---\s*page\s*\d+\s*---", re.IGNORECASE)
STATUTORY_REFERENCE_RE = re.compile(
    rf"(?:又依|爰依|依據|依照|依)(?P<law_name>[一-龥]{{1,20}}?(?:法|條例|規則|辦法|準則|要點))"
    rf"(?P<article>第{ARTICLE_NUMBER_PATTERN}條(?:第{ARTICLE_NUMBER_PATTERN}項)?)"
)
MAX_STATEMENTS_PER_PACKET = 2
MAX_LEGAL_REFERENCES_PER_PACKET = 2
MAX_STATEMENT_TEXT_CHARS = 300
MAX_EVIDENCE_QUOTE_CHARS = 300
MAX_STATEMENTS_BY_CATEGORY = {
    "background": 4,
    "applicant_position": 4,
    "respondent_position": 4,
    "core_issue": 4,
    "reasoning": 6,
    "decision_result": 4,
}
REASONING_SIGNAL_RE = re.compile(r"經查|從而|是以|準此|足認|應認|尚難|尚非無據|本中心|職故|綜上")
CASE_APPLICATION_SIGNAL_RE = re.compile(r"由上可知|從而|足認|難認|尚難|尚非無據|無請求權|有據|無理由|有理由")
POSITION_SIGNAL_RE = re.compile(r"請求|主張|拒絕|爭議|無理由|應給付|應返還|不同意")


SECTION_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "statements": {
            "type": "array",
            "maxItems": MAX_STATEMENTS_PER_PACKET,
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": sorted(SUMMARY_CATEGORIES)},
                    "text": {"type": "string", "maxLength": MAX_STATEMENT_TEXT_CHARS},
                    "evidence_quote": {"type": "string", "maxLength": MAX_EVIDENCE_QUOTE_CHARS},
                },
                "required": ["category", "text", "evidence_quote"],
            },
        },
        "legal_references": {
            "type": "array",
            "maxItems": MAX_LEGAL_REFERENCES_PER_PACKET,
            "items": {
                "type": "object",
                "properties": {
                    "law_name": {"type": "string", "maxLength": 50},
                    "article": {"type": "string", "maxLength": 50},
                    "evidence_quote": {"type": "string", "maxLength": MAX_EVIDENCE_QUOTE_CHARS},
                },
                "required": ["law_name", "article", "evidence_quote"],
            },
        },
    },
    "required": ["statements", "legal_references"],
}

_GROUNDED_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "maxLength": 600},
        "statement_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
    },
    "required": ["text", "statement_ids"],
}

FINAL_SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "background": _GROUNDED_ITEM_SCHEMA,
        "applicant_position": _GROUNDED_ITEM_SCHEMA,
        "respondent_position": _GROUNDED_ITEM_SCHEMA,
        "core_issues": {"type": "array", "items": _GROUNDED_ITEM_SCHEMA, "maxItems": 4},
        "reasoning_points": {"type": "array", "items": _GROUNDED_ITEM_SCHEMA, "maxItems": 6},
        "decision_result": _GROUNDED_ITEM_SCHEMA,
    },
    "required": [
        "background",
        "applicant_position",
        "respondent_position",
        "core_issues",
        "reasoning_points",
        "decision_result",
    ],
}


class SummaryGenerationError(RuntimeError):
    """Raised when local summary generation is unavailable or returns unsafe output."""


@dataclass(frozen=True)
class StructuredGeneration:
    """A parsed model response plus non-sensitive local runtime metrics."""

    content: dict[str, Any]
    metrics: dict[str, Any]


@dataclass(frozen=True)
class SourcePacket:
    """A bounded, exact slice of one source section sent to the local model."""

    section_id: str
    section_type: str
    title: str
    part_index: int
    start_offset: int
    end_offset: int
    text: str


class SummaryProvider(Protocol):
    provider_name: str
    model_name: str

    def ensure_model_available(self) -> dict[str, Any]:
        pass

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> StructuredGeneration:
        pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_evidence(value: str) -> str:
    """Remove layout-only whitespace and PDF page markers for evidence checks."""

    without_page_markers = PAGE_ARTIFACT_RE.sub("", value or "")
    return re.sub(r"\s+", "", without_page_markers)


def normalize_evidence_quote(value: str) -> str:
    """Remove model-added quote wrappers without allowing semantic fuzzy matches."""

    normalized = normalize_evidence(value).strip("「」『』\"'“”‘’")
    return re.sub(r"(?:…|\.{3})+$", "", normalized)


def validate_local_ollama_url(base_url: str) -> str:
    """Reject remote endpoints so this provider cannot silently become a paid API client."""

    normalized = base_url.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme != "http" or parsed.hostname not in ALLOWED_LOCAL_HOSTS:
        raise SummaryGenerationError(
            "OLLAMA_BASE_URL must use local HTTP only: http://127.0.0.1:11434 or http://localhost:11434."
        )
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SummaryGenerationError("OLLAMA_BASE_URL must not contain credentials, query parameters, or fragments.")
    return normalized


def validate_local_model_name(model_name: str) -> str:
    """Block Ollama cloud tags even if the local server has cloud access configured."""

    normalized = model_name.strip()
    if not normalized:
        raise SummaryGenerationError("SUMMARY_MODEL must not be empty.")
    if normalized.lower().endswith(":cloud"):
        raise SummaryGenerationError("Cloud Ollama models are disabled; choose a downloaded local model tag.")
    return normalized


class OllamaLocalSummaryProvider:
    """Call an Ollama server that is constrained to this machine.

    No token or Authorization header is accepted. Model availability is checked
    through the local `/api/tags` inventory before case text is submitted.
    """

    provider_name = OLLAMA_LOCAL_PROVIDER

    def __init__(
        self,
        *,
        model_name: str = SUMMARY_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        timeout_seconds: int = SUMMARY_REQUEST_TIMEOUT_SECONDS,
        num_ctx: int = SUMMARY_NUM_CTX,
        max_output_tokens: int = SUMMARY_MAX_OUTPUT_TOKENS,
        client: httpx.Client | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise SummaryGenerationError("SUMMARY_REQUEST_TIMEOUT_SECONDS must be greater than 0.")
        if num_ctx < 2048:
            raise SummaryGenerationError("SUMMARY_NUM_CTX must be at least 2048.")
        if max_output_tokens < 256:
            raise SummaryGenerationError("SUMMARY_MAX_OUTPUT_TOKENS must be at least 256.")
        self.model_name = validate_local_model_name(model_name)
        self.base_url = validate_local_ollama_url(base_url)
        self.timeout_seconds = timeout_seconds
        self.num_ctx = num_ctx
        self.max_output_tokens = max_output_tokens
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> OllamaLocalSummaryProvider:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def ensure_model_available(self) -> dict[str, Any]:
        try:
            response = self._client.get(f"{self.base_url}/api/tags", timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise SummaryGenerationError(
                f"Local Ollama is unavailable at {self.base_url}. Start Ollama before running the summary trial."
            ) from error

        models = payload.get("models") if isinstance(payload, dict) else None
        names = {
            str(model.get("name", "")).strip()
            for model in models or []
            if isinstance(model, dict) and model.get("name")
        }
        if self.model_name not in names:
            raise SummaryGenerationError(
                f"Local model '{self.model_name}' is not installed. Available local models: {sorted(names)}"
            )
        return {"provider": self.provider_name, "model": self.model_name, "available_models": sorted(names)}

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> StructuredGeneration:
        request_payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "think": False,
            "format": schema,
            # num_predict prevents malformed structured output from generating
            # indefinitely and consuming the entire request timeout.
            "options": {
                "temperature": 0,
                "num_ctx": self.num_ctx,
                "num_predict": self.max_output_tokens,
            },
        }
        started_at = time.perf_counter()
        try:
            response = self._client.post(
                f"{self.base_url}/api/chat",
                json=request_payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as error:
            raise SummaryGenerationError(
                f"Local Ollama request timed out after {self.timeout_seconds} seconds for model '{self.model_name}'."
            ) from error
        except httpx.HTTPStatusError as error:
            raise SummaryGenerationError(
                f"Local Ollama request failed with HTTP {error.response.status_code} for model '{self.model_name}'."
            ) from error
        except (httpx.HTTPError, ValueError) as error:
            raise SummaryGenerationError(f"Local Ollama request failed for model '{self.model_name}'.") from error

        message = payload.get("message") if isinstance(payload, dict) else None
        raw_content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(raw_content, str) or not raw_content.strip():
            raise SummaryGenerationError("Local Ollama returned an empty structured response.")
        try:
            content = json.loads(raw_content)
        except json.JSONDecodeError as error:
            raise SummaryGenerationError("Local Ollama returned invalid JSON despite structured output mode.") from error
        if not isinstance(content, dict):
            raise SummaryGenerationError("Local Ollama structured response must be a JSON object.")

        return StructuredGeneration(
            content=content,
            metrics={
                "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "prompt_eval_count": payload.get("prompt_eval_count"),
                "eval_count": payload.get("eval_count"),
                "load_duration_ns": payload.get("load_duration"),
            },
        )


def create_summary_provider(
    *,
    provider_name: str = SUMMARY_PROVIDER,
    model_name: str = SUMMARY_MODEL,
    base_url: str = OLLAMA_BASE_URL,
    timeout_seconds: int = SUMMARY_REQUEST_TIMEOUT_SECONDS,
    num_ctx: int = SUMMARY_NUM_CTX,
    max_output_tokens: int = SUMMARY_MAX_OUTPUT_TOKENS,
) -> OllamaLocalSummaryProvider:
    resolved_provider = provider_name.strip().lower()
    if resolved_provider != OLLAMA_LOCAL_PROVIDER:
        raise SummaryGenerationError(
            f"Unsupported summary provider '{resolved_provider}'. Only '{OLLAMA_LOCAL_PROVIDER}' is enabled."
        )
    return OllamaLocalSummaryProvider(
        model_name=model_name,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        num_ctx=num_ctx,
        max_output_tokens=max_output_tokens,
    )


def split_text_exact(text: str, *, max_chars: int) -> list[tuple[int, int, str]]:
    """Split long sections near sentence boundaries without dropping source characters."""

    if max_chars <= 0:
        raise ValueError("max_chars must be greater than 0.")
    if not text:
        return []

    parts: list[tuple[int, int, str]] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            lower_bound = start + max_chars // 4
            # PDF extraction inserts visual line wraps inside sentences, so
            # newline is not a semantic boundary. Prefer actual punctuation.
            boundary = max(text.rfind(mark, lower_bound, end) for mark in "。！？；")
            if boundary >= lower_bound:
                end = boundary + 1
        parts.append((start, end, text[start:end]))
        start = end

    if "".join(part[2] for part in parts) != text:
        raise AssertionError("Source packet splitting did not preserve the complete input text.")
    return parts


def build_source_packets(
    structured_document: dict[str, Any],
    *,
    max_chars: int = SUMMARY_SECTION_MAX_CHARS,
) -> list[SourcePacket]:
    """Build bounded prompts from relevant sections while retaining exact offsets."""

    packets: list[SourcePacket] = []
    for section in structured_document.get("sections", []):
        if section.get("section_type") not in SUMMARY_SECTION_TYPES:
            continue
        section_text = str(section.get("content") or "")
        for part_index, (start, end, text) in enumerate(split_text_exact(section_text, max_chars=max_chars), start=1):
            packets.append(
                SourcePacket(
                    section_id=str(section["section_id"]),
                    section_type=str(section["section_type"]),
                    title=str(section["title"]),
                    part_index=part_index,
                    start_offset=int(section["start_offset"]) + start,
                    end_offset=int(section["start_offset"]) + end,
                    text=text,
                )
            )
    return packets


def _section_system_prompt() -> str:
    return (
        "你是保險評議決定書的中立資料整理助手。只可整理使用者提供的原文，不得加入常識推測、"
        "法律意見或原文沒有的事實。每個陳述都必須附上一段可在原文逐字核對的 evidence_quote。"
        "法源只可列正式法規名稱與條號；保單、附約及個別契約條款不是法源。"
        "區塊名稱與指定類別是角色判斷依據，不可自行改成其他類別。所有 text 必須使用繁體中文；"
        "evidence_quote 必須直接複製原文，不可翻譯、改字或截斷句子。輸出必須符合 JSON schema。"
    )


def _section_user_prompt(case_metadata: dict[str, Any], packet: SourcePacket) -> str:
    metadata = {
        "case_number": case_metadata.get("case_number"),
        "decision_date": case_metadata.get("decision_date"),
        "dispute_type": case_metadata.get("dispute_type"),
    }
    expected_category = SUMMARY_CATEGORY_BY_SECTION_TYPE[packet.section_type]
    return (
        "請從下列單一原文區塊擷取可用於案件摘要的陳述，最多兩項；法源最多兩項。每項 text 與 evidence_quote "
        "都不得超過三百字。evidence_quote 須包含足以理解該陳述的完整原句，同一引文只可出現一次。"
        "沒有可用陳述時 statements 請回傳空陣列。"
        f"本區塊所有 statements.category 必須固定為 {expected_category}，不可使用其他類別。\n"
        "若指定類別為 reasoning，優先擷取本中心如何把規則套用至本案事實，以及因此得出的判斷；"
        "純法條文字應放在 legal_references，不要取代本案具體理由。\n"
        "不要把表格列、借還款明細列、頁碼或只有數字的清單當成摘要陳述。\n"
        f"案件資料：{json.dumps(metadata, ensure_ascii=False)}\n"
        f"區塊：{packet.title}（{packet.section_type}，第 {packet.part_index} 段）\n"
        "--- 原文開始 ---\n"
        f"{packet.text}\n"
        "--- 原文結束 ---"
    )


def _final_system_prompt() -> str:
    return (
        "你是保險評議案件摘要編輯。只能改寫輸入的已驗證陳述，每個摘要欄位必須引用一個或多個"
        "statement_ids，不可增加新事實、法律判斷或保單條款。文字要中立、精簡，清楚區分申請人與相對人。"
        "申請人主張只能引用 applicant_position，相對人主張只能引用 respondent_position，"
        "評議理由只能引用 reasoning。不可跨類別引用，並須使用繁體中文。輸出必須符合 JSON schema。"
    )


def _final_user_prompt(case_metadata: dict[str, Any], statements: list[dict[str, Any]]) -> str:
    metadata = {
        "case_number": case_metadata.get("case_number"),
        "decision_date": case_metadata.get("decision_date"),
        "dispute_type": case_metadata.get("dispute_type"),
    }
    compact_statements = [
        {
            "statement_id": item["statement_id"],
            "category": item["category"],
            "text": item["text"],
            "section_title": item["section_title"],
        }
        for item in statements
    ]
    return (
        "請將已驗證陳述整理成案件摘要。若某欄沒有足夠陳述，text 請填空字串且 statement_ids 填空陣列。\n"
        f"案件資料：{json.dumps(metadata, ensure_ascii=False)}\n"
        f"已驗證陳述：{json.dumps(compact_statements, ensure_ascii=False)}"
    )


def _is_supported_quote(quote: str, source_text: str) -> bool:
    normalized_quote = normalize_evidence_quote(quote)
    return bool(normalized_quote) and normalized_quote in normalize_evidence(source_text)


def _expand_quote_to_sentence(quote: str, source_text: str) -> str:
    """Expand an exact quote fragment to source sentence boundaries when bounded."""

    normalized_quote = normalize_evidence_quote(quote)
    normalized_source = normalize_evidence(source_text)
    quote_start = normalized_source.find(normalized_quote)
    if quote_start < 0:
        return normalized_quote
    previous_boundaries = [normalized_source.rfind(mark, 0, quote_start) for mark in "。！？；"]
    sentence_start = max(previous_boundaries) + 1
    quote_end = quote_start + len(normalized_quote)
    if normalized_quote[-1] in "。！？；":
        sentence_end = quote_end
    else:
        following_boundaries = [
            boundary
            for mark in "。！？；"
            if (boundary := normalized_source.find(mark, quote_end)) >= 0
        ]
        sentence_end = min(following_boundaries) + 1 if following_boundaries else quote_end
    expanded = normalized_source[sentence_start:sentence_end]
    return expanded if len(expanded) <= MAX_EVIDENCE_QUOTE_CHARS else normalized_quote


def _is_table_like_statement(value: str) -> bool:
    """Reject OCR table rows that contain many numbers but little prose."""

    compact = normalize_evidence(value)
    if len(compact) < 20:
        return False
    digit_count = sum(character.isdigit() for character in compact)
    chinese_count = sum("\u4e00" <= character <= "\u9fff" for character in compact)
    return digit_count >= 10 and chinese_count / len(compact) < 0.35


def _has_complete_statement_ending(value: str) -> bool:
    """Require a visible sentence boundary so source excerpts do not end mid-word."""

    normalized = normalize_evidence_quote(value)
    return bool(normalized) and normalized[-1] in "。！？；"


def _validated_statement(
    raw: Any,
    *,
    packet: SourcePacket,
    statement_id: str,
) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    model_category = str(raw.get("category") or "").strip()
    category = SUMMARY_CATEGORY_BY_SECTION_TYPE.get(packet.section_type)
    text = str(raw.get("text") or "").strip()
    evidence_quote = str(raw.get("evidence_quote") or "").strip()
    safe_evidence_quote = _expand_quote_to_sentence(evidence_quote, packet.text)
    if (
        category not in SUMMARY_CATEGORIES
        or model_category not in SUMMARY_CATEGORIES
        or not text
        or len(text) > MAX_STATEMENT_TEXT_CHARS
        or len(evidence_quote) > MAX_EVIDENCE_QUOTE_CHARS
        or not _is_supported_quote(evidence_quote, packet.text)
        or _is_table_like_statement(safe_evidence_quote)
        or not _has_complete_statement_ending(safe_evidence_quote)
    ):
        return None
    # Prefer an extractive statement whenever the model's paraphrase cannot be
    # verified verbatim. This prevents polarity changes such as "must pay"
    # becoming "has paid" while retaining a concise model-selected source quote.
    safe_text = safe_evidence_quote
    return {
        "statement_id": statement_id,
        "category": category,
        "model_category": model_category,
        "category_corrected": model_category != category,
        "text": safe_text,
        "model_text": text,
        "text_replaced_with_quote": normalize_evidence(text) != safe_text,
        "source_fallback": False,
        "section_id": packet.section_id,
        "section_type": packet.section_type,
        "section_title": packet.title,
        "part_index": packet.part_index,
        "source_start_offset": packet.start_offset,
        "source_end_offset": packet.end_offset,
        "evidence_quote": safe_evidence_quote,
    }


def _source_fallback_statement(*, packet: SourcePacket, statement_id: str) -> dict[str, Any] | None:
    """Use a complete short section when the model fails to extract any valid item."""

    source_text = normalize_evidence(packet.text)
    category = SUMMARY_CATEGORY_BY_SECTION_TYPE.get(packet.section_type)
    if not source_text or category not in SUMMARY_CATEGORIES:
        return None
    if len(source_text) > MAX_STATEMENT_TEXT_CHARS:
        if category not in {"applicant_position", "respondent_position"}:
            return None
        candidate = source_text[:MAX_STATEMENT_TEXT_CHARS]
        # End at a complete sentence when possible so a long party statement
        # remains readable without inventing an ellipsis or paraphrase.
        boundary = max(candidate.rfind(mark) for mark in "。！？；")
        source_text = candidate[: boundary + 1] if boundary >= 100 else candidate
    return {
        "statement_id": statement_id,
        "category": category,
        "model_category": None,
        "category_corrected": False,
        "text": source_text,
        "model_text": None,
        "text_replaced_with_quote": False,
        "source_fallback": True,
        "section_id": packet.section_id,
        "section_type": packet.section_type,
        "section_title": packet.title,
        "part_index": packet.part_index,
        "source_start_offset": packet.start_offset,
        "source_end_offset": packet.end_offset,
        "evidence_quote": source_text,
    }


def _extract_reasoning_signal_statements(structured_document: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract complete case-application sentences from the full reasoning section."""

    statements: list[dict[str, Any]] = []
    for section in structured_document.get("sections", []):
        if section.get("section_type") != "reasoning":
            continue
        source_text = normalize_evidence(str(section.get("content") or ""))
        for match in re.finditer(r"[^。！？；]{20,300}[。！？；]", source_text):
            sentence = match.group(0)
            if not CASE_APPLICATION_SIGNAL_RE.search(sentence) or _is_table_like_statement(sentence):
                continue
            # Quoted statutes often contain internal periods; unmatched quote
            # marks indicate the regex stopped before the complete proposition.
            if sentence.count("「") != sentence.count("」") or sentence.count("『") != sentence.count("』"):
                continue
            signal_score = sum(
                weight
                for signal, weight in (
                    ("從而", 8),
                    ("難認", 6),
                    ("有據", 5),
                    ("由上可知", 4),
                    ("足認", 4),
                    ("無請求權", 4),
                    ("申請人", 2),
                    ("相對人", 2),
                )
                if signal in sentence
            )
            statements.append(
                {
                    "category": "reasoning",
                    "model_category": None,
                    "category_corrected": False,
                    "text": sentence,
                    "model_text": None,
                    "text_replaced_with_quote": False,
                    "source_fallback": False,
                    "rule_based_reasoning": True,
                    "reasoning_signal_score": signal_score,
                    "section_id": str(section["section_id"]),
                    "section_type": "reasoning",
                    "section_title": str(section["title"]),
                    "part_index": 0,
                    "source_start_offset": int(section["start_offset"]),
                    "source_end_offset": int(section["end_offset"]),
                    "evidence_quote": sentence,
                }
            )
    return statements


def _validated_legal_reference(raw: Any, *, packet: SourcePacket) -> dict[str, Any] | None:
    """Accept only source-grounded statutes; policy or contract references are excluded."""

    if not isinstance(raw, dict):
        return None
    law_name = str(raw.get("law_name") or "").strip()
    article = str(raw.get("article") or "").strip()
    evidence_quote = str(raw.get("evidence_quote") or "").strip()
    safe_evidence_quote = normalize_evidence_quote(evidence_quote)
    normalized_source = normalize_evidence(packet.text)
    article_match = ARTICLE_RE.search(normalize_evidence(article))
    if (
        not law_name
        or not LAW_NAME_RE.search(law_name)
        or POLICY_REFERENCE_RE.search(law_name)
        or article_match is None
        or normalize_evidence(law_name) not in normalized_source
        or normalize_evidence(article) not in normalized_source
        or not _is_supported_quote(evidence_quote, packet.text)
    ):
        return None
    return {
        "law_name": law_name,
        "article": article_match.group(0),
        "section_id": packet.section_id,
        "section_title": packet.title,
        "evidence_quote": safe_evidence_quote,
        "extraction_source": "model_validated",
    }


def _extract_statutory_references(packet: SourcePacket) -> list[dict[str, Any]]:
    """Extract explicit statutory citations that the local model may omit."""

    source_text = normalize_evidence(packet.text)
    references: list[dict[str, Any]] = []
    for match in STATUTORY_REFERENCE_RE.finditer(source_text):
        law_name = match.group("law_name")
        article = match.group("article")
        if POLICY_REFERENCE_RE.search(law_name):
            continue
        references.append(
            {
                "law_name": law_name,
                "article": article,
                "section_id": packet.section_id,
                "section_title": packet.title,
                "evidence_quote": match.group(0),
                "extraction_source": "rule_based",
            }
        )
    return references


def _grounded_item(
    raw: Any,
    statement_map: dict[str, dict[str, Any]],
    *,
    allowed_categories: set[str],
    allow_fallback: bool = True,
    max_statement_count: int = 3,
    preferred_section_types: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Resolve model-selected IDs and rebuild text from validated statements.

    The merge model chooses relevant IDs, but its free-form text is not trusted.
    Rebuilding from validated extraction statements keeps every displayed sentence
    tied to an evidence quote. A deterministic same-category fallback prevents an
    otherwise valid case from showing an unexplained empty field.
    """

    raw_ids = raw.get("statement_ids") if isinstance(raw, dict) else None
    statement_ids = []
    if isinstance(raw_ids, list):
        statement_ids = list(
            dict.fromkeys(
                str(item)
                for item in raw_ids
                if str(item) in statement_map and statement_map[str(item)]["category"] in allowed_categories
            )
        )
    if not statement_ids and allow_fallback:
        statement_ids = [
            statement_id
            for statement_id, statement in statement_map.items()
            if statement["category"] in allowed_categories
        ]
    if preferred_section_types:
        priority = {section_type: index for index, section_type in enumerate(preferred_section_types)}
        statement_ids.sort(
            key=lambda statement_id: priority.get(
                statement_map[statement_id]["section_type"],
                len(priority),
            )
        )
    statement_ids = statement_ids[:max_statement_count]
    texts = list(
        dict.fromkeys(
            statement_map[statement_id]["text"].strip()
            for statement_id in statement_ids
            if statement_map[statement_id]["text"].strip()
        )
    )
    if not texts or not statement_ids:
        return {"text": None, "statement_ids": []}
    return {"text": " ".join(texts), "statement_ids": statement_ids}


def _grounded_items(
    raw: Any,
    statement_map: dict[str, dict[str, Any]],
    *,
    allowed_categories: set[str],
    max_items: int,
) -> list[dict[str, Any]]:
    raw_items = raw if isinstance(raw, list) else []
    items = [
        _grounded_item(
            item,
            statement_map,
            allowed_categories=allowed_categories,
            allow_fallback=False,
            max_statement_count=1,
        )
        for item in raw_items
    ]
    items = [item for item in items if item["text"]]
    if not items:
        # Keep separate bullets when the merge model omits a list entirely.
        items = [
            {"text": statement["text"], "statement_ids": [statement_id]}
            for statement_id, statement in statement_map.items()
            if statement["category"] in allowed_categories
        ]

    deduplicated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = normalize_evidence(item["text"])
        if key and key not in seen:
            deduplicated.append(item)
            seen.add(key)
    return deduplicated[:max_items]


def _ranked_grounded_items(
    statement_map: dict[str, dict[str, Any]],
    *,
    allowed_categories: set[str],
    max_items: int,
) -> list[dict[str, Any]]:
    """Select high-signal evidence deterministically instead of trusting merge prose."""

    ranked_ids = [
        statement_id
        for statement_id, statement in sorted(
            statement_map.items(),
            key=lambda pair: -_statement_priority(pair[1]),
        )
        if statement["category"] in allowed_categories
    ]
    raw_items = [{"statement_ids": [statement_id]} for statement_id in ranked_ids]
    return _grounded_items(
        raw_items,
        statement_map,
        allowed_categories=allowed_categories,
        max_items=max_items,
    )


def _deduplicate_statements(statements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the longest source quote when same-category evidence overlaps."""

    deduplicated: list[dict[str, Any]] = []
    for statement in statements:
        quote = normalize_evidence(statement["evidence_quote"])
        overlapping_index = next(
            (
                index
                for index, existing in enumerate(deduplicated)
                if existing["category"] == statement["category"]
                and (
                    quote in normalize_evidence(existing["evidence_quote"])
                    or normalize_evidence(existing["evidence_quote"]) in quote
                )
            ),
            None,
        )
        if overlapping_index is None:
            deduplicated.append(statement)
            continue
        existing_quote = normalize_evidence(deduplicated[overlapping_index]["evidence_quote"])
        if len(quote) > len(existing_quote):
            deduplicated[overlapping_index] = statement
    return deduplicated


def _balance_statements_for_merge(statements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bound the merge prompt while retaining evidence from every summary category."""

    counts = {category: 0 for category in SUMMARY_CATEGORIES}
    selected: list[dict[str, Any]] = []
    # Application-specific conclusions should survive the per-category cap even
    # when they occur after long quoted rules or contract provisions.
    ranked = sorted(
        enumerate(statements),
        key=lambda pair: (-_statement_priority(pair[1]), pair[0]),
    )
    for _, statement in ranked:
        category = statement["category"]
        if counts[category] >= MAX_STATEMENTS_BY_CATEGORY[category]:
            continue
        selected.append(statement)
        counts[category] += 1
    return selected


def _statement_priority(statement: dict[str, Any]) -> int:
    """Rank prose with case application signals above generic rules and tables."""

    text = str(statement.get("text") or "")
    category = statement.get("category")
    score = 0
    if category == "reasoning" and REASONING_SIGNAL_RE.search(text):
        score += 10
    if statement.get("rule_based_reasoning"):
        signal_score = int(statement.get("reasoning_signal_score") or 0)
        score += 20 + signal_score + (5 if signal_score > 0 else 0)
    if category == "reasoning" and CONTRACT_QUOTE_RE.search(text) and not CASE_APPLICATION_SIGNAL_RE.search(text):
        score -= 5
    if category in {"applicant_position", "respondent_position"} and POSITION_SIGNAL_RE.search(text):
        score += 6
    if statement.get("source_fallback"):
        score -= 1
    if _is_table_like_statement(text):
        score -= 20
    return score


def _deduplicate_legal_references(references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduplicated: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for reference in references:
        key = (normalize_evidence(reference["law_name"]), normalize_evidence(reference["article"]))
        if key not in seen:
            deduplicated.append(reference)
            seen.add(key)
    return deduplicated


def generate_case_summary(
    *,
    case_metadata: dict[str, Any],
    structured_document: dict[str, Any],
    provider: SummaryProvider,
    max_section_chars: int = SUMMARY_SECTION_MAX_CHARS,
) -> dict[str, Any]:
    """Generate an evidence-grounded summary without writing to the case database."""

    packets = build_source_packets(structured_document, max_chars=max_section_chars)
    if not packets:
        raise SummaryGenerationError("No supported document sections were available for summary generation.")

    statements: list[dict[str, Any]] = []
    legal_references: list[dict[str, Any]] = []
    request_metrics: list[dict[str, Any]] = []
    rejected_statement_count = 0
    rejected_legal_reference_count = 0
    attempted_request_count = 0
    request_errors: list[dict[str, Any]] = []

    for packet in packets:
        attempted_request_count += 1
        try:
            response = provider.generate_structured(
                system_prompt=_section_system_prompt(),
                user_prompt=_section_user_prompt(case_metadata, packet),
                schema=SECTION_EXTRACTION_SCHEMA,
            )
        except SummaryGenerationError as error:
            # Preserve a diagnosable partial result rather than discarding every
            # successful packet in a long case because one generation failed.
            request_errors.append(
                {
                    "stage": "section_extraction",
                    "section_id": packet.section_id,
                    "section_type": packet.section_type,
                    "part_index": packet.part_index,
                    "message": str(error),
                }
            )
            fallback = _source_fallback_statement(
                packet=packet,
                statement_id=f"statement_{len(statements) + 1:04d}",
            )
            if fallback is not None:
                statements.append(fallback)
            continue
        request_metrics.append(response.metrics)
        raw_statements = response.content.get("statements")
        bounded_statements = raw_statements[:MAX_STATEMENTS_PER_PACKET] if isinstance(raw_statements, list) else []
        accepted_before_packet = len(statements)
        for raw in bounded_statements:
            statement = _validated_statement(
                raw,
                packet=packet,
                statement_id=f"statement_{len(statements) + 1:04d}",
            )
            if statement is None:
                rejected_statement_count += 1
            else:
                statements.append(statement)

        if len(statements) == accepted_before_packet:
            # Short, already-structured sections are safer to preserve verbatim
            # than to expose an empty role, issue, or decision field.
            fallback = _source_fallback_statement(
                packet=packet,
                statement_id=f"statement_{len(statements) + 1:04d}",
            )
            if fallback is not None:
                statements.append(fallback)

        raw_references = response.content.get("legal_references")
        for raw in raw_references if isinstance(raw_references, list) else []:
            reference = _validated_legal_reference(raw, packet=packet)
            if reference is None:
                rejected_legal_reference_count += 1
            else:
                legal_references.append(reference)
        # Statutory citation syntax is deterministic, so supplement model output
        # with a source-only parser and de-duplicate both sources at the end.
        legal_references.extend(_extract_statutory_references(packet))

    for statement in _extract_reasoning_signal_statements(structured_document):
        statement["statement_id"] = f"statement_{len(statements) + 1:04d}"
        statements.append(statement)

    if not statements:
        raise SummaryGenerationError("The local model produced no source-grounded statements.")

    deduplicated_statements = _deduplicate_statements(statements)
    merge_statements = _balance_statements_for_merge(deduplicated_statements)

    attempted_request_count += 1
    final_merge_fallback = False
    try:
        final_response = provider.generate_structured(
            system_prompt=_final_system_prompt(),
            user_prompt=_final_user_prompt(case_metadata, merge_statements),
            schema=FINAL_SUMMARY_SCHEMA,
        )
        request_metrics.append(final_response.metrics)
        final_content = final_response.content
    except SummaryGenerationError as error:
        # Every field resolver has a same-category fallback, so a failed merge
        # can still produce an auditable extractive summary.
        final_merge_fallback = True
        final_content = {}
        request_errors.append({"stage": "final_merge", "message": str(error)})
    statement_map = {item["statement_id"]: item for item in merge_statements}
    background = _grounded_item(
        final_content.get("background"),
        statement_map,
        allowed_categories={"background"},
    )
    applicant_position = _grounded_item(
        final_content.get("applicant_position"),
        statement_map,
        allowed_categories={"applicant_position"},
        max_statement_count=2,
    )
    respondent_position = _grounded_item(
        final_content.get("respondent_position"),
        statement_map,
        allowed_categories={"respondent_position"},
        max_statement_count=2,
    )
    core_issues = _grounded_items(
        final_content.get("core_issues"),
        statement_map,
        allowed_categories={"core_issue"},
        max_items=MAX_STATEMENTS_BY_CATEGORY["core_issue"],
    )
    reasoning_points = _ranked_grounded_items(
        statement_map,
        allowed_categories={"reasoning"},
        max_items=3,
    )
    decision_result = _grounded_item(
        final_content.get("decision_result"),
        statement_map,
        allowed_categories={"decision_result"},
        max_statement_count=2,
        preferred_section_types=("holding", "disposition", "conclusion"),
    )

    used_statement_ids = list(
        dict.fromkeys(
            statement_id
            for item in (background, applicant_position, respondent_position, decision_result, *core_issues, *reasoning_points)
            for statement_id in item["statement_ids"]
        )
    )
    evidence = [statement_map[statement_id] for statement_id in used_statement_ids]
    source_text = "".join(str(section.get("content") or "") for section in structured_document.get("sections", []))

    return {
        "case_id": case_metadata.get("case_id"),
        "case_number": case_metadata.get("case_number"),
        "summary": {
            "background": background["text"],
            "applicant_position": applicant_position["text"],
            "respondent_position": respondent_position["text"],
            "core_issues": [item["text"] for item in core_issues],
            "reasoning_points": [item["text"] for item in reasoning_points],
            "decision_result": decision_result["text"],
            "legal_references": _deduplicate_legal_references(legal_references),
            "evidence": evidence,
        },
        "generation": {
            "provider": provider.provider_name,
            "model": provider.model_name,
            "prompt_version": PROMPT_VERSION,
            "source_hash_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            "source_chars": len(source_text),
            "packet_count": len(packets),
            "request_count": len(request_metrics),
            "attempted_request_count": attempted_request_count,
            "failed_request_count": len(request_errors),
            "request_errors": request_errors,
            "final_merge_fallback": final_merge_fallback,
            "reasoning_selection": "deterministic_signal_ranked",
            "validated_statement_count": len(statements),
            "deduplicated_statement_count": len(deduplicated_statements),
            "duplicate_statement_count": len(statements) - len(deduplicated_statements),
            "corrected_category_count": sum(bool(item.get("category_corrected")) for item in statements),
            "extractive_fallback_count": sum(bool(item.get("text_replaced_with_quote")) for item in statements),
            "source_fallback_count": sum(bool(item.get("source_fallback")) for item in statements),
            "rule_based_reasoning_count": sum(bool(item.get("rule_based_reasoning")) for item in statements),
            "statement_counts_by_category": {
                category: sum(item["category"] == category for item in deduplicated_statements)
                for category in sorted(SUMMARY_CATEGORIES)
            },
            "merge_statement_count": len(merge_statements),
            "rejected_statement_count": rejected_statement_count,
            "rejected_legal_reference_count": rejected_legal_reference_count,
            "review_status": "unreviewed",
            "generated_at": utc_now_iso(),
            "request_metrics": request_metrics,
        },
    }
