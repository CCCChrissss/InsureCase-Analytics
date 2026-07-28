import React from "react";
import { AlertTriangle, Database, FileSearch } from "lucide-react";

import { apiGet, apiPath } from "../api/client";
import { AsyncBlock, Metric, PageHeader, PanelHeader } from "../components/ui";
import { useAsyncData } from "../hooks/useAsyncData";
import type { SearchResponse } from "../types";

function matchSourceLabel(source: string) {
  if (source === "fts5") return "FTS5";
  if (source === "like_fallback_empty_fts5") return "LIKE 補查";
  if (source === "like_fallback_error") return "LIKE fallback";
  return source;
}

function matchSourceDescription(source: string) {
  if (source === "fts5") return "由 SQLite FTS5 MATCH 直接命中。";
  if (source === "like_fallback_empty_fts5") return "FTS5 未找到結果後，用 LIKE 對中文全文補查。";
  if (source === "like_fallback_error") return "FTS5 查詢發生錯誤後，用 LIKE fallback。";
  return "由搜尋服務回傳的命中來源。";
}

function matchSourceClass(source: string) {
  if (source === "fts5") return "source-badge fts5";
  if (source === "like_fallback_empty_fts5") return "source-badge like-empty";
  if (source === "like_fallback_error") return "source-badge like-error";
  return "source-badge";
}

export function SearchPage({ onOpenCase }: { onOpenCase: (caseId: string) => void }) {
  const [query, setQuery] = React.useState("癌症");
  const [submittedQuery, setSubmittedQuery] = React.useState("癌症");
  const results = useAsyncData(
    () => apiGet<SearchResponse>(apiPath("/search", { q: submittedQuery, page_size: 20 })),
    [submittedQuery]
  );
  const sourceSummary = React.useMemo(() => {
    const sources = new Map<string, number>();
    (results.data?.items ?? []).forEach((item) => {
      sources.set(item.match_source, (sources.get(item.match_source) ?? 0) + 1);
    });
    return Array.from(sources.entries())
      .map(([source, count]) => `${matchSourceLabel(source)} ${count}`)
      .join(" / ");
  }, [results.data?.items]);

  return (
    <section className="page">
      <PageHeader
        title="全文搜尋"
        description="搜尋 normalized text，顯示命中片段、案件來源與 FTS5 / LIKE fallback 判讀依據。"
      />
      <form
        className="search-form"
        onSubmit={(event) => {
          event.preventDefault();
          setSubmittedQuery(query.trim() || "癌症");
        }}
      >
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="輸入關鍵字，例如 癌症、除外責任、手術" />
        <button className="primary-button" type="submit">搜尋</button>
      </form>

      <AsyncBlock loading={results.loading} error={results.error}>
        {results.data && (
          <div className="metric-grid search-metrics">
            <Metric label="查詢文字" value={results.data.query} />
            <Metric label="總命中案件" value={results.data.total.toLocaleString("zh-TW")} />
            <Metric label="本頁顯示" value={`${results.data.items.length} 筆`} />
            <Metric label="命中來源" value={sourceSummary || "無結果"} />
          </div>
        )}
      </AsyncBlock>

      <section className="panel">
        <PanelHeader title="搜尋判讀方式" />
        <div className="search-method-grid">
          <div>
            <Database size={18} />
            <strong>FTS5 優先</strong>
            <span>先用 SQLite FTS5 MATCH 查詢全文索引，速度快，適合一般關鍵字。</span>
          </div>
          <div>
            <FileSearch size={18} />
            <strong>中文補查</strong>
            <span>若 FTS5 沒報錯但 0 筆，會再用 LIKE 對 normalized text 補查，降低中文漏查。</span>
          </div>
          <div>
            <AlertTriangle size={18} />
            <strong>錯誤 fallback</strong>
            <span>若 FTS5 query 觸發 OperationalError，會改用 LIKE，結果來源會標示為 fallback。</span>
          </div>
        </div>
      </section>

      <section className="panel">
        <PanelHeader title={`搜尋結果 ${results.data ? `(${results.data.total})` : ""}`} />
        <AsyncBlock loading={results.loading} error={results.error}>
          <div className="search-results">
            {(results.data?.items ?? []).map((item) => (
              <button key={item.case_id} className="result-row" type="button" onClick={() => onOpenCase(item.case_id)}>
                <span className="result-head">
                  <span className="case-number">{item.case_number}</span>
                  <span className={matchSourceClass(item.match_source)} title={matchSourceDescription(item.match_source)}>
                    {matchSourceLabel(item.match_source)}
                  </span>
                </span>
                <span className="case-meta">{item.decision_date ?? "無日期"} · {item.dispute_type ?? "無爭議類型"}</span>
                <span className="source-explain">{matchSourceDescription(item.match_source)}</span>
                <span className="snippet">{item.snippet || "此結果沒有可顯示的命中文字片段。"}</span>
              </button>
            ))}
            {results.data?.items.length === 0 && (
              <div className="state-box">目前沒有符合條件的全文搜尋結果。</div>
            )}
          </div>
        </AsyncBlock>
      </section>
    </section>
  );
}
