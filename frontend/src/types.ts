export type HealthResponse = {
  status: string;
  database_ready: boolean;
};

export type OverviewStatistics = {
  case_count: number;
  dispute_type_count: number;
  roc_years: number[];
  first_decision_date: string | null;
  last_decision_date: string | null;
};

export type CountItem = {
  name: string;
  count: number;
};

export type CaseSummary = {
  case_id: string;
  case_number: string;
  roc_year: number;
  decision_date: string | null;
  decision_category: string | null;
  decision_result: string | null;
  industry: string | null;
  industry_subcategory: string | null;
  dispute_type: string | null;
  pdf_path: string | null;
  normalized_text_path: string | null;
};

export type PaginatedCases = {
  items: CaseSummary[];
  total: number;
  page: number;
  page_size: number;
};

export type CaseDetail = CaseSummary & {
  source_pdf_url: string | null;
  case_directory: string | null;
  raw_text_path: string | null;
  metadata_path: string | null;
  raw_text: string | null;
  normalized_text: string | null;
  raw_text_chars: number | null;
  normalized_text_chars: number | null;
  page_count: number | null;
  extraction_method: string | null;
};

export type DocumentSection = {
  section_id: string;
  section_type: string;
  title: string;
  heading: string | null;
  content: string;
  order: number;
  char_count: number;
  start_offset: number;
  end_offset: number;
};

export type CaseDocumentSections = {
  case_id: string;
  source_type: "normalized" | "raw";
  source_chars: number;
  covered_chars: number;
  complete_coverage: boolean;
  sections: DocumentSection[];
};

export type AiSummaryLegalReference = {
  law_name: string;
  article: string;
  section_title: string | null;
  evidence_quote: string;
};

export type AiSummaryEvidence = {
  category: string;
  text: string;
  section_title: string | null;
  evidence_quote: string;
};

// This type mirrors the read-only review response; no browser-side mutation
// contract exists until authentication and audit logging are implemented.
export type AiCaseSummaryDetail = {
  summary_id: string;
  case_id: string;
  summary: {
    background: string;
    applicant_position: string;
    respondent_position: string;
    core_issues: string[];
    reasoning_points: string[];
    decision_result: string;
    legal_references: AiSummaryLegalReference[];
    evidence: AiSummaryEvidence[];
  };
  provider: string;
  model: string;
  prompt_version: string;
  source_sha256: string;
  review_status: "unreviewed" | "approved" | "rejected";
  official: boolean;
  generated_at: string;
  reviewed_at: string | null;
};

export type AiCaseSummaryResponse = {
  case_id: string;
  available: boolean;
  item: AiCaseSummaryDetail | null;
};

export type SimilarCase = {
  case_id: string;
  case_number: string;
  decision_date: string | null;
  dispute_type: string | null;
  decision_result: string | null;
  score: number;
  matched_reasons: string[];
};

export type SimilarCasesResponse = {
  case_id: string;
  items: SimilarCase[];
  total_candidates: number;
};

export type SearchResult = {
  case_id: string;
  case_number: string;
  decision_date: string | null;
  dispute_type: string | null;
  decision_result: string | null;
  snippet: string | null;
  match_source: string;
};

export type SearchResponse = {
  items: SearchResult[];
  total: number;
  query: string;
  page: number;
  page_size: number;
};

export type SemanticSearchResult = {
  chunk_id: string;
  case_id: string;
  case_number: string;
  decision_date: string | null;
  dispute_type: string | null;
  section_hint: string | null;
  chunk_index: number;
  score: number;
  chunk_text: string;
};

export type SemanticSearchResponse = {
  query: string;
  embedding_provider: string;
  embedding_model: string;
  embedding_dims: number;
  embedding_device: string;
  elapsed_ms: number;
  items: SemanticSearchResult[];
  total_candidates: number;
};

export type SemanticCaseScore = {
  case_id: string;
  score: number;
  section_hint: string | null;
  chunk_index: number;
  chunk_text: string;
};

export type SemanticCaseScoresResponse = {
  query: string;
  embedding_provider: string;
  embedding_model: string;
  embedding_dims: number;
  embedding_device: string;
  elapsed_ms: number;
  items: SemanticCaseScore[];
  total_candidates: number;
};

export type SemanticRankedSearchResult = SearchResult & {
  // 分數與段落皆來自該案件中最接近查詢的 chunk。
  similarity_score: number | null;
  section_hint: string | null;
  chunk_index: number | null;
  semantic_snippet: string | null;
};

export type SemanticRankedSearchResponse = {
  query: string;
  embedding_provider: string;
  embedding_model: string;
  embedding_dims: number;
  embedding_device: string;
  elapsed_ms: number;
  cached: boolean;
  items: SemanticRankedSearchResult[];
  total: number;
  total_candidates: number;
  match_source: string;
  page: number;
  page_size: number;
};

export type EmbeddingModelStatus = {
  embedding_model: string;
  embedding_dims: number;
  embedding_count: number;
  suggested_provider: string;
};

export type EmbeddingStatusResponse = {
  database_name: string;
  configured_provider: string;
  configured_model: string;
  local_bge_requested_device: string;
  models: EmbeddingModelStatus[];
};

export type QuerySuggestionResponse = {
  available: boolean;
  original_query: string;
  suggested_query: string | null;
  rule_id: string | null;
  explanation: string | null;
  auto_apply: boolean;
};

export type SemanticSimilarChunk = {
  chunk_id: string;
  section_hint: string | null;
  chunk_index: number;
  score: number;
  chunk_text: string;
};

export type SemanticSimilarCase = {
  case_id: string;
  case_number: string;
  decision_date: string | null;
  dispute_type: string | null;
  score: number;
  matched_chunks: SemanticSimilarChunk[];
};

export type SemanticSimilarCasesResponse = {
  case_id: string;
  embedding_model: string;
  source_chunk_count: number;
  items: SemanticSimilarCase[];
  total_candidates: number;
};

export type QualityReport = {
  report_title: string;
  report_date: string;
  method_version: string;
  scope: {
    roc_year: number;
    case_count: number;
    dispute_type_count: number;
    formal_database_case_count: number;
    formal_database_year_distribution: Record<string, number>;
  };
  top_dispute_types: CountItem[];
  summary_field_stats: Array<{
    field: string;
    non_empty: number;
    min_length: number;
    median_length: number;
    average_length: number;
    max_length: number;
  }>;
  contamination_checks: Array<{
    name: string;
    issue_count: number;
  }>;
  scoring_rules: Array<{
    name: string;
    points: number;
    description: string;
  }>;
  sample_cases: Array<{
    case_number: string;
    dispute_type: string;
    decision_date: string;
    holding_length: number;
    applicant_claim_length: number;
    reasoning_length: number;
    top5_same_dispute_type_count: number;
  }>;
  similar_stats: {
    evaluated_cases: number;
    top1_same_dispute_type: number;
    top1_same_dispute_type_rate: number;
    top5_contains_same_dispute_type: number;
    top5_contains_same_dispute_type_rate: number;
    average_same_type_count_in_top5: number;
    min_same_type_count_in_top5: number;
  };
  known_exceptions: Array<{
    case_number: string;
    dispute_type: string;
    decision_date: string;
    reason: string;
  }>;
  conclusions: Array<{
    title: string;
    items: string[];
  }>;
  limitations: string[];
  next_steps: string[];
};

export type Route = "dashboard" | "cases" | "search" | "methodology" | "semantic" | "quality";
