import React from "react";
import { ChevronLeft, ChevronRight, FileText, Info, Search } from "lucide-react";

import { apiPost } from "../api/client";
import { SimilarityExplanationDialog } from "../components/SimilarityExplanationDialog";
import { AsyncBlock, PageHeader } from "../components/ui";
import { LOCAL_BGE_MODEL, LOCAL_BGE_PROVIDER } from "../config/semantic";
import { useAsyncData } from "../hooks/useAsyncData";
import type {
  HybridSearchResponse,
  HybridSearchResult,
} from "../types";

const PAGE_SIZE_OPTIONS = [10, 15, 20] as const;
type SearchResultScope = "all" | "keyword";
type SearchSortDirection = "desc" | "asc";

export function SearchPage({ onOpenCase }: { onOpenCase: (caseId: string, label?: string) => void }) {
  const [query, setQuery] = React.useState("");
  const [submittedQuery, setSubmittedQuery] = React.useState("");
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(15);
  const [resultScope, setResultScope] = React.useState<SearchResultScope>("all");
  const [sortDirection, setSortDirection] = React.useState<SearchSortDirection>("desc");
  const [showSimilarityExplanation, setShowSimilarityExplanation] = React.useState(false);

  // 查找範圍與排序方向都交給後端在完整排名上處理，避免只重排目前頁面。
  const hybridResults = useAsyncData(
    () => submittedQuery
      ? apiPost<HybridSearchResponse>("/hybrid-search", {
          q: submittedQuery,
          page,
          page_size: pageSize,
          embedding_provider: LOCAL_BGE_PROVIDER,
          embedding_model: LOCAL_BGE_MODEL,
          result_scope: resultScope,
          sort_direction: sortDirection,
        })
      : Promise.resolve<HybridSearchResponse | null>(null),
    [submittedQuery, page, pageSize, resultScope, sortDirection]
  );

  // useAsyncData 會保留舊資料，需連查找範圍與方向一起核對，避免短暫顯示舊順序。
  const validHybridResults = isCurrentPage(
    hybridResults.data,
    submittedQuery,
    page,
    pageSize,
    resultScope,
    sortDirection
  )
    ? hybridResults.data
    : null;
  const totalPages = Math.max(1, Math.ceil((validHybridResults?.total ?? 0) / pageSize));

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
            placeholder="輸入關鍵字、短句，或描述事故與拒賠經過"
            aria-label="搜尋案件全文"
            maxLength={2000}
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
                {validHybridResults
                  ? resultCountText(validHybridResults, page, totalPages)
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
                <span>查找範圍</span>
                <select
                  value={resultScope}
                  onChange={(event) => {
                    setPage(1);
                    setResultScope(event.target.value as SearchResultScope);
                  }}
                >
                  <option value="all">全部相關案件</option>
                  <option value="keyword">只看文字命中</option>
                </select>
              </label>
              <label className="result-size-control sort-control">
                <span>排序方向</span>
                <select
                  value={sortDirection}
                  onChange={(event) => {
                    setPage(1);
                    setSortDirection(event.target.value as SearchSortDirection);
                  }}
                >
                  <option value="desc">相關度高到低</option>
                  <option value="asc">相關度低到高</option>
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
          {hybridResults.loading && (
            <div className="semantic-status-note">正在比較全部案件的語意，並合併文字命中結果</div>
          )}
          {validHybridResults?.search_mode === "keyword_fallback" && (
            <div className="semantic-unavailable-note" title={validHybridResults.fallback_reason ?? undefined}>
              本機語意模型目前無法使用，已自動改用精確文字搜尋。
            </div>
          )}
          <AsyncBlock loading={hybridResults.loading} error={hybridResults.error}>
            <div className="claims-search-results">
              {(validHybridResults?.items ?? []).map((item) => (
                <button
                  key={item.case_id}
                  className="claims-search-row"
                  type="button"
                  onClick={() => onOpenCase(item.case_id, item.case_number)}
                >
                  <span className="search-row-heading">
                    <strong>{item.case_number}</strong>
                    <SimilarityValue score={item.similarity_score} />
                  </span>
                  <span className="search-row-meta">
                    <span>
                      <span className="search-row-dispute">{item.dispute_type || "爭議類型未標示"}</span>
                      <span className="search-row-date">{item.decision_date || "日期未標示"}</span>
                      <MatchTypeValue matchType={item.match_type} />
                    </span>
                    <strong className={`search-decision-result ${decisionTone(item.decision_result)}`}>
                      評議結果：{meaningfulDecisionResult(item.decision_result)}
                    </strong>
                  </span>
                  <p>{item.snippet || "此案件沒有可顯示的命中片段。"}</p>
                </button>
              ))}
              {validHybridResults?.items.length === 0 && (
                <div className="state-box">目前沒有符合「{submittedQuery}」的案件，請嘗試較短的關鍵字。</div>
              )}
            </div>
            {(validHybridResults?.total ?? 0) > 0 && (
              <div className="pagination compact-pagination search-pagination">
                <button
                  className="icon-button"
                  type="button"
                  disabled={page <= 1 || hybridResults.loading}
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
                  disabled={page >= totalPages || hybridResults.loading}
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

// 查詢、頁碼、範圍與方向都一致時，資料才屬於目前畫面。
function isCurrentPage<T extends HybridSearchResponse>(
  data: T | null,
  query: string,
  page: number,
  pageSize: number,
  resultScope: SearchResultScope,
  sortDirection: SearchSortDirection
): data is T {
  return Boolean(
    data
    && data.query === query
    && data.page === page
    && data.page_size === pageSize
    && data.result_scope === resultScope
    && data.sort_direction === sortDirection
  );
}

function MatchTypeValue({ matchType }: { matchType: HybridSearchResult["match_type"] }) {
  const labels = {
    hybrid: "語意相近・文字也命中",
    semantic: "語意相近",
    keyword: "文字命中",
  } as const;
  return <span className={`search-match-type ${matchType}`}>{labels[matchType]}</span>;
}

function resultCountText(
  result: HybridSearchResponse,
  page: number,
  totalPages: number
) {
  if (result.search_mode === "hybrid" && result.result_scope === "all") {
    return `已排序 ${result.total.toLocaleString("zh-TW")} 件，其中 ${result.keyword_match_count.toLocaleString("zh-TW")} 件也有文字命中，第 ${page} / ${totalPages} 頁`;
  }
  return `共 ${result.total.toLocaleString("zh-TW")} 件，第 ${page} / ${totalPages} 頁`;
}

function SimilarityValue({ score }: { score: number | null }) {
  // 後端保留原始 cosine score，畫面只做 0 到 100 的保守百分比轉換。
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
