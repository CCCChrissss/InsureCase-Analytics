import React from "react";
import { ChevronLeft, ChevronRight, FileText, Info, Search } from "lucide-react";

import { apiGet, apiPath } from "../api/client";
import { SimilarityExplanationDialog } from "../components/SimilarityExplanationDialog";
import { AsyncBlock, PageHeader } from "../components/ui";
import { LOCAL_BGE_MODEL, LOCAL_BGE_PROVIDER } from "../config/semantic";
import { useAsyncData } from "../hooks/useAsyncData";
import type {
  SearchResponse,
  SearchResult,
  SemanticCaseScoresResponse,
  SemanticRankedSearchResponse,
  SemanticRankedSearchResult,
} from "../types";

const PAGE_SIZE_OPTIONS = [10, 15, 20] as const;
type SearchSortMode = "keyword" | "similarity";

export function SearchPage({ onOpenCase }: { onOpenCase: (caseId: string, label?: string) => void }) {
  const [query, setQuery] = React.useState("");
  const [submittedQuery, setSubmittedQuery] = React.useState("");
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(15);
  const [sortMode, setSortMode] = React.useState<SearchSortMode>("keyword");
  const [showSimilarityExplanation, setShowSimilarityExplanation] = React.useState(false);

  // 關鍵字搜尋永遠保留為基線，讓本機語意模型失敗時仍可完成查找與翻頁。
  const keywordResults = useAsyncData(
    () => submittedQuery
      ? apiGet<SearchResponse>(apiPath("/search", { q: submittedQuery, page, page_size: pageSize }))
      : Promise.resolve<SearchResponse | null>(null),
    [submittedQuery, page, pageSize]
  );
  const rankedResults = useAsyncData(
    () => submittedQuery && sortMode === "similarity"
      ? apiGet<SemanticRankedSearchResponse>(apiPath("/semantic-ranked-search", {
          q: submittedQuery,
          page,
          page_size: pageSize,
          embedding_provider: LOCAL_BGE_PROVIDER,
          embedding_model: LOCAL_BGE_MODEL,
        }))
      : Promise.resolve<SemanticRankedSearchResponse | null>(null),
    [submittedQuery, page, pageSize, sortMode]
  );

  // useAsyncData 在新請求期間會保留舊資料，因此必須比對查詢與頁碼，避免畫面短暫顯示錯頁。
  const validKeywordResults = isCurrentPage(keywordResults.data, submittedQuery, page, pageSize)
    ? keywordResults.data
    : null;
  const validRankedResults = isCurrentPage(rankedResults.data, submittedQuery, page, pageSize)
    ? rankedResults.data
    : null;
  const fallbackToKeyword = sortMode === "similarity" && Boolean(rankedResults.error);
  const usesKeywordResults = sortMode === "keyword" || fallbackToKeyword;
  const activeResults = usesKeywordResults ? validKeywordResults : validRankedResults;
  const activeLoading = usesKeywordResults ? keywordResults.loading : rankedResults.loading;
  const activeError = usesKeywordResults ? keywordResults.error : rankedResults.error;

  // 關鍵字排序只對當頁補相似度；全域排序 API 已直接回傳每筆案件分數，不需重算。
  const scoreCaseIds = React.useMemo(() => {
    if (!usesKeywordResults || keywordResults.loading || !validKeywordResults) return "";
    return validKeywordResults.items.map((item) => item.case_id).join(",");
  }, [keywordResults.loading, usesKeywordResults, validKeywordResults]);
  const semanticScores = useAsyncData(
    () => scoreCaseIds
      ? apiGet<SemanticCaseScoresResponse>(apiPath("/semantic-case-scores", {
          q: submittedQuery,
          case_ids: scoreCaseIds,
          embedding_provider: LOCAL_BGE_PROVIDER,
          embedding_model: LOCAL_BGE_MODEL,
        }))
      : Promise.resolve<SemanticCaseScoresResponse | null>(null),
    [scoreCaseIds, submittedQuery]
  );
  const scoreByCase = React.useMemo(
    () => new Map((semanticScores.data?.items ?? []).map((item) => [item.case_id, item.score])),
    [semanticScores.data]
  );
  const totalPages = Math.max(1, Math.ceil((activeResults?.total ?? 0) / pageSize));

  return (
    <section className="page claims-search-page">
      <PageHeader
        title="案件全文搜尋"
        description="輸入疾病、醫療處置、保單條款或理賠爭點，查找決定書中的相關案件。"
      />
      <form
        className="claims-search-form"
        onSubmit={(event) => {
          event.preventDefault();
          setPage(1);
          setSubmittedQuery(query.trim());
        }}
      >
        <div className="input-with-icon">
          <Search size={19} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="例如：癌症、除外責任、剖腹產、失能保險金"
            aria-label="搜尋案件全文"
          />
        </div>
        <button className="primary-button" type="submit" disabled={!query.trim()}>
          <Search size={17} />
          搜尋
        </button>
      </form>

      {!submittedQuery && (
        <div className="search-start-state">
          <FileText size={30} />
          <h3>從案件原文查找理賠參考</h3>
          <p>搜尋結果會顯示命中的案件、評議結果及與搜尋內容的接近程度。</p>
        </div>
      )}

      {submittedQuery && (
        <section className="search-result-section">
          <div className="workspace-section-header search-results-header">
            <div>
              <h3>搜尋結果</h3>
              <span>
                {activeResults
                  ? `共 ${activeResults.total.toLocaleString("zh-TW")} 件，第 ${page} / ${totalPages} 頁`
                  : "查詢中"}
              </span>
            </div>
            <div className="search-results-controls">
              <button
                className="secondary-button compact-button"
                type="button"
                onClick={() => setShowSimilarityExplanation(true)}
              >
                <Info size={16} />
                相似度怎麼看
              </button>
              <label className="result-size-control sort-control">
                <span>排序方式</span>
                <select
                  value={sortMode}
                  onChange={(event) => {
                    setPage(1);
                    setSortMode(event.target.value as SearchSortMode);
                  }}
                >
                  <option value="keyword">關鍵字相關性</option>
                  <option value="similarity">相似度：高到低</option>
                </select>
              </label>
              <label className="result-size-control">
                <span>每頁顯示</span>
                <select
                  value={pageSize}
                  onChange={(event) => {
                    setPage(1);
                    setPageSize(Number(event.target.value));
                  }}
                >
                  {PAGE_SIZE_OPTIONS.map((value) => (
                    <option key={value} value={value}>{value} 筆</option>
                  ))}
                </select>
              </label>
            </div>
          </div>
          {sortMode === "similarity" && rankedResults.loading && (
            <div className="semantic-status-note">正在計算全部命中案件的相似度並重新排序</div>
          )}
          {fallbackToKeyword && (
            <div className="semantic-unavailable-note" title={rankedResults.error ?? undefined}>
              全域相似度排序目前無法使用，已改用關鍵字相關性排序。
            </div>
          )}
          {!activeLoading && scoreCaseIds && semanticScores.loading && (
            <div className="semantic-status-note">正在補上每筆案件的相似度</div>
          )}
          {!activeLoading && usesKeywordResults && semanticScores.error && (
            <div className="semantic-unavailable-note" title={semanticScores.error}>
              相似度目前無法使用，全文搜尋與翻頁仍可正常使用。
            </div>
          )}
          <AsyncBlock loading={activeLoading} error={activeError}>
            <div className="claims-search-results">
              {(activeResults?.items ?? []).map((item) => (
                <button
                  key={item.case_id}
                  className="claims-search-row"
                  type="button"
                  onClick={() => onOpenCase(item.case_id, item.case_number)}
                >
                  <span className="search-row-heading">
                    <strong>{item.case_number}</strong>
                    <SimilarityValue
                      score={similarityForItem(item, scoreByCase)}
                      loading={usesKeywordResults && semanticScores.loading}
                    />
                  </span>
                  <span className="search-row-meta">
                    <span>
                      <span className="search-row-dispute">{item.dispute_type || "爭議類型未標示"}</span>
                      <span className="search-row-date">{item.decision_date || "日期未標示"}</span>
                    </span>
                    <strong className={`search-decision-result ${decisionTone(item.decision_result)}`}>
                      評議結果：{meaningfulDecisionResult(item.decision_result)}
                    </strong>
                  </span>
                  <p>{item.snippet || "此案件沒有可顯示的命中片段。"}</p>
                </button>
              ))}
              {activeResults?.items.length === 0 && (
                <div className="state-box">目前沒有符合「{submittedQuery}」的案件，請嘗試較短的關鍵字。</div>
              )}
            </div>
            {(activeResults?.total ?? 0) > 0 && (
              <div className="pagination compact-pagination search-pagination">
                <button
                  className="icon-button"
                  type="button"
                  disabled={page <= 1 || activeLoading}
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                  aria-label="上一頁"
                  title="上一頁"
                >
                  <ChevronLeft size={18} />
                </button>
                <span>第 {page} 頁，共 {totalPages} 頁</span>
                <button
                  className="icon-button"
                  type="button"
                  disabled={page >= totalPages || activeLoading}
                  onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                  aria-label="下一頁"
                  title="下一頁"
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            )}
          </AsyncBlock>
        </section>
      )}

      <SimilarityExplanationDialog
        open={showSimilarityExplanation}
        onClose={() => setShowSimilarityExplanation(false)}
      />
    </section>
  );
}

// 只有查詢、頁碼及每頁筆數都一致時，資料才屬於目前畫面。
function isCurrentPage<T extends { query: string; page: number; page_size: number }>(
  data: T | null,
  query: string,
  page: number,
  pageSize: number
): data is T {
  return Boolean(data && data.query === query && data.page === page && data.page_size === pageSize);
}

// 全域排序結果直接帶分數；一般搜尋結果則使用當頁補算的分數表。
function similarityForItem(
  item: SearchResult | SemanticRankedSearchResult,
  scoreByCase: Map<string, number>
) {
  if ("similarity_score" in item) return item.similarity_score;
  return scoreByCase.get(item.case_id) ?? null;
}

function SimilarityValue({ score, loading }: { score: number | null; loading: boolean }) {
  // 後端保留原始 cosine score，畫面只做 0 到 100 的保守百分比轉換。
  if (loading) return <span className="search-similarity pending">相似度計算中</span>;
  if (score === null) return null;
  const percentage = Math.round(Math.min(Math.max(score, 0), 1) * 100);
  return <span className="search-similarity">與搜尋內容相近 {percentage}%</span>;
}

function meaningfulDecisionResult(value: string | null) {
  // metadata 的「全部」是查詢條件，不是案件結論，因此不可直接呈現為評議結果。
  const cleaned = value?.trim();
  return cleaned && cleaned !== "全部" ? cleaned : "尚未整理";
}

function decisionTone(value: string | null) {
  // 色彩只協助掃讀，不改變或推論後端提供的評議結果文字。
  if (!value) return "neutral";
  if (/部分有理由/.test(value)) return "partial";
  if (/無理由|駁回|不受理/.test(value)) return "adverse";
  if (/有理由/.test(value)) return "favorable";
  return "neutral";
}
