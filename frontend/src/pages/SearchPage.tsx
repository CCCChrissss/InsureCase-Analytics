import React from "react";
import { ChevronLeft, ChevronRight, FileText, Info, Search } from "lucide-react";

import { apiGet, apiPath } from "../api/client";
import { SimilarityExplanationDialog } from "../components/SimilarityExplanationDialog";
import { AsyncBlock, PageHeader } from "../components/ui";
import { LOCAL_BGE_MODEL, LOCAL_BGE_PROVIDER } from "../config/semantic";
import { useAsyncData } from "../hooks/useAsyncData";
import type { SearchResponse, SemanticCaseScore, SemanticCaseScoresResponse } from "../types";

const PAGE_SIZE_OPTIONS = [10, 15, 20] as const;

export function SearchPage({ onOpenCase }: { onOpenCase: (caseId: string, label?: string) => void }) {
  const [query, setQuery] = React.useState("");
  const [submittedQuery, setSubmittedQuery] = React.useState("");
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(15);
  const [showSimilarityExplanation, setShowSimilarityExplanation] = React.useState(false);

  const results = useAsyncData(
    () => submittedQuery
      ? apiGet<SearchResponse>(apiPath("/search", { q: submittedQuery, page, page_size: pageSize }))
      : Promise.resolve<SearchResponse | null>(null),
    [submittedQuery, page, pageSize]
  );
  const scoreCaseIds = React.useMemo(() => {
    if (
      results.loading
      || !results.data
      || results.data.query !== submittedQuery
      || results.data.page !== page
      || results.data.page_size !== pageSize
    ) {
      return "";
    }
    return results.data.items.map((item) => item.case_id).join(",");
  }, [page, pageSize, results.data, results.loading, submittedQuery]);
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
    () => new Map((semanticScores.data?.items ?? []).map((item) => [item.case_id, item])),
    [semanticScores.data]
  );
  const totalPages = Math.max(1, Math.ceil((results.data?.total ?? 0) / pageSize));

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
                {results.data
                  ? `共 ${results.data.total.toLocaleString("zh-TW")} 件，第 ${page} / ${totalPages} 頁`
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
          {!results.loading && scoreCaseIds && semanticScores.loading && (
            <div className="semantic-status-note">正在補上每筆案件的相似度</div>
          )}
          {!results.loading && semanticScores.error && (
            <div className="semantic-unavailable-note" title={semanticScores.error}>
              相似度目前無法使用，全文搜尋與翻頁仍可正常使用。
            </div>
          )}
          <AsyncBlock loading={results.loading} error={results.error}>
            <div className="claims-search-results">
              {(results.data?.items ?? []).map((item) => (
                <button
                  key={item.case_id}
                  className="claims-search-row"
                  type="button"
                  onClick={() => onOpenCase(item.case_id, item.case_number)}
                >
                  <span className="search-row-heading">
                    <strong>{item.case_number}</strong>
                    <SimilarityValue score={scoreByCase.get(item.case_id)} loading={semanticScores.loading} />
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
              {results.data?.items.length === 0 && (
                <div className="state-box">目前沒有符合「{submittedQuery}」的案件，請嘗試較短的關鍵字。</div>
              )}
            </div>
            {(results.data?.total ?? 0) > 0 && (
              <div className="pagination compact-pagination search-pagination">
                <button
                  className="icon-button"
                  type="button"
                  disabled={page <= 1 || results.loading}
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
                  disabled={page >= totalPages || results.loading}
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

function SimilarityValue({ score, loading }: { score: SemanticCaseScore | undefined; loading: boolean }) {
  if (loading) return <span className="search-similarity pending">相似度計算中</span>;
  if (!score) return null;
  const percentage = Math.round(Math.min(Math.max(score.score, 0), 1) * 100);
  return <span className="search-similarity">與搜尋內容相近 {percentage}%</span>;
}

function meaningfulDecisionResult(value: string | null) {
  const cleaned = value?.trim();
  return cleaned && cleaned !== "全部" ? cleaned : "尚未整理";
}

function decisionTone(value: string | null) {
  if (!value) return "neutral";
  if (/部分有理由/.test(value)) return "partial";
  if (/無理由|駁回|不受理/.test(value)) return "adverse";
  if (/有理由/.test(value)) return "favorable";
  return "neutral";
}
