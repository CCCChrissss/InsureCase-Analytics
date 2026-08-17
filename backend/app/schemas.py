from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    database_ready: bool


class CaseSummary(BaseModel):
    case_id: str
    case_number: str
    roc_year: int
    decision_date: str | None
    decision_category: str | None
    decision_result: str | None
    industry: str | None
    industry_subcategory: str | None
    dispute_type: str | None
    pdf_path: str | None
    normalized_text_path: str | None


class PaginatedCases(BaseModel):
    items: list[CaseSummary]
    total: int
    page: int
    page_size: int


class CaseDetail(CaseSummary):
    source_pdf_url: str | None
    case_directory: str | None
    raw_text_path: str | None
    metadata_path: str | None
    raw_text: str | None
    normalized_text: str | None
    raw_text_chars: int | None
    normalized_text_chars: int | None
    page_count: int | None
    extraction_method: str | None


class DocumentSection(BaseModel):
    section_id: str
    section_type: str
    title: str
    heading: str | None
    content: str
    order: int
    char_count: int
    start_offset: int
    end_offset: int


class CaseDocumentSections(BaseModel):
    case_id: str
    source_type: str
    source_chars: int
    covered_chars: int
    complete_coverage: bool
    sections: list[DocumentSection]


class CaseSummaryDetail(BaseModel):
    case_id: str
    holding: str | None
    applicant_claim: str | None
    reasoning: str | None
    summary_method: str | None
    created_at: str | None


class AiSummaryLegalReference(BaseModel):
    law_name: str
    article: str
    section_title: str | None = None
    evidence_quote: str


class AiSummaryEvidence(BaseModel):
    category: str
    text: str
    section_title: str | None = None
    evidence_quote: str


class AiSummaryContent(BaseModel):
    """User-facing fields only; model diagnostics remain in generation_json."""

    background: str
    applicant_position: str
    respondent_position: str
    core_issues: list[str]
    reasoning_points: list[str]
    decision_result: str
    legal_references: list[AiSummaryLegalReference]
    evidence: list[AiSummaryEvidence]


class AiCaseSummaryDetail(BaseModel):
    summary_id: str
    case_id: str
    summary: AiSummaryContent
    provider: str
    model: str
    prompt_version: str
    source_sha256: str
    review_status: str
    official: bool
    generated_at: str
    reviewed_at: str | None


class AiCaseSummaryResponse(BaseModel):
    """Use an availability wrapper so missing POC summaries are not API errors."""

    case_id: str
    available: bool
    item: AiCaseSummaryDetail | None


class SimilarCase(BaseModel):
    case_id: str
    case_number: str
    decision_date: str | None
    dispute_type: str | None
    decision_result: str | None
    score: float
    matched_reasons: list[str]


class SimilarCasesResponse(BaseModel):
    case_id: str
    items: list[SimilarCase]
    total_candidates: int


class SearchResult(BaseModel):
    case_id: str
    case_number: str
    decision_date: str | None
    dispute_type: str | None
    decision_result: str | None
    snippet: str | None
    match_source: str


class SearchResponse(BaseModel):
    items: list[SearchResult]
    total: int
    query: str
    page: int
    page_size: int


class SemanticSearchResult(BaseModel):
    chunk_id: str
    case_id: str
    case_number: str
    decision_date: str | None
    dispute_type: str | None
    section_hint: str | None
    chunk_index: int
    score: float
    chunk_text: str


class SemanticSearchResponse(BaseModel):
    query: str
    embedding_provider: str
    embedding_model: str
    embedding_dims: int
    embedding_device: str
    elapsed_ms: float
    items: list[SemanticSearchResult]
    total_candidates: int


class SemanticCaseScore(BaseModel):
    case_id: str
    score: float
    section_hint: str | None
    chunk_index: int
    chunk_text: str


class SemanticCaseScoresResponse(BaseModel):
    query: str
    embedding_provider: str
    embedding_model: str
    embedding_dims: int
    embedding_device: str
    elapsed_ms: float
    items: list[SemanticCaseScore]
    total_candidates: int


class SemanticRankedSearchResult(SearchResult):
    """Keyword search item enriched with its best matching semantic chunk."""
    similarity_score: float | None
    section_hint: str | None
    chunk_index: int | None
    semantic_snippet: str | None


class SemanticRankedSearchResponse(BaseModel):
    """Globally ranked semantic results after keyword filtering and pagination."""
    query: str
    embedding_provider: str
    embedding_model: str
    embedding_dims: int
    embedding_device: str
    elapsed_ms: float
    cached: bool
    items: list[SemanticRankedSearchResult]
    total: int
    total_candidates: int
    match_source: str
    page: int
    page_size: int


class HybridSearchResult(SearchResult):
    """One case ranked by semantic recall plus optional literal matching."""

    similarity_score: float | None
    ranking_score: float
    semantic_rank: int | None
    keyword_rank: int | None
    section_hint: str | None
    chunk_index: int | None
    semantic_snippet: str | None
    match_type: str


class HybridSearchRequest(BaseModel):
    """JSON body avoids URL-length limits for a user's incident narrative."""

    q: str = Field(min_length=1, max_length=2000)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=20)
    embedding_model: str | None = Field(default=None, min_length=1)
    embedding_provider: str | None = Field(default=None, min_length=1)


class HybridSearchResponse(BaseModel):
    """Paginated complete hybrid ranking and its auditable runtime metadata."""

    query: str
    embedding_provider: str
    embedding_model: str
    embedding_dims: int
    embedding_device: str
    elapsed_ms: float
    cached: bool
    search_mode: str
    fallback_reason: str | None
    items: list[HybridSearchResult]
    total: int
    keyword_match_count: int
    semantic_case_count: int
    total_candidates: int
    match_source: str
    page: int
    page_size: int


class EmbeddingModelStatus(BaseModel):
    embedding_model: str
    embedding_dims: int
    embedding_count: int
    suggested_provider: str


class EmbeddingStatusResponse(BaseModel):
    database_name: str
    configured_provider: str
    configured_model: str
    local_bge_requested_device: str
    models: list[EmbeddingModelStatus]


class QuerySuggestionResponse(BaseModel):
    available: bool
    original_query: str
    suggested_query: str | None
    rule_id: str | None
    explanation: str | None
    auto_apply: bool


class SemanticSimilarChunk(BaseModel):
    chunk_id: str
    section_hint: str | None
    chunk_index: int
    score: float
    chunk_text: str


class SemanticSimilarCase(BaseModel):
    case_id: str
    case_number: str
    decision_date: str | None
    dispute_type: str | None
    score: float
    matched_chunks: list[SemanticSimilarChunk]


class SemanticSimilarCasesResponse(BaseModel):
    case_id: str
    embedding_model: str
    source_chunk_count: int
    items: list[SemanticSimilarCase]
    total_candidates: int


class OverviewStatistics(BaseModel):
    case_count: int
    dispute_type_count: int
    roc_years: list[int]
    first_decision_date: str | None
    last_decision_date: str | None


class CountItem(BaseModel):
    name: str
    count: int


class QualityScope(BaseModel):
    roc_year: int
    case_count: int
    dispute_type_count: int
    formal_database_case_count: int
    formal_database_year_distribution: dict[str, int]


class QualitySummaryFieldStat(BaseModel):
    field: str
    non_empty: int
    min_length: int
    median_length: float
    average_length: float
    max_length: int


class QualityContaminationCheck(BaseModel):
    name: str
    issue_count: int


class QualityScoringRule(BaseModel):
    name: str
    points: int
    description: str


class QualitySampleCase(BaseModel):
    case_number: str
    dispute_type: str
    decision_date: str
    holding_length: int
    applicant_claim_length: int
    reasoning_length: int
    top5_same_dispute_type_count: int


class QualitySimilarStats(BaseModel):
    evaluated_cases: int
    top1_same_dispute_type: int
    top1_same_dispute_type_rate: float
    top5_contains_same_dispute_type: int
    top5_contains_same_dispute_type_rate: float
    average_same_type_count_in_top5: float
    min_same_type_count_in_top5: int


class QualityKnownException(BaseModel):
    case_number: str
    dispute_type: str
    decision_date: str
    reason: str


class QualityConclusion(BaseModel):
    title: str
    items: list[str]


class QualityReport(BaseModel):
    report_title: str
    report_date: str
    method_version: str
    scope: QualityScope
    top_dispute_types: list[CountItem]
    summary_field_stats: list[QualitySummaryFieldStat]
    contamination_checks: list[QualityContaminationCheck]
    scoring_rules: list[QualityScoringRule]
    sample_cases: list[QualitySampleCase]
    similar_stats: QualitySimilarStats
    known_exceptions: list[QualityKnownException]
    conclusions: list[QualityConclusion]
    limitations: list[str]
    next_steps: list[str]
