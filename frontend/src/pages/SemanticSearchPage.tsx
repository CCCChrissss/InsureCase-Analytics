import React from "react";
import { BrainCircuit, FileText, Search } from "lucide-react";

import { apiGet, apiPath } from "../api/client";
import { AsyncBlock, Metric, PageHeader, PanelHeader } from "../components/ui";
import { useAsyncData } from "../hooks/useAsyncData";
import type { SemanticSearchResponse } from "../types";

function formatScore(score: number) {
  return score.toFixed(4);
}

function shortText(value: string, maxLength = 420) {
  return value.length > maxLength ? `${value.slice(0, maxLength)}...` : value;
}

export function SemanticSearchPage({ onOpenCase }: { onOpenCase: (caseId: string) => void }) {
  const [query, setQuery] = React.useState("癌症保險金");
  const [submittedQuery, setSubmittedQuery] = React.useState("癌症保險金");
  const [limit, setLimit] = React.useState(10);
  const results = useAsyncData(
    () => apiGet<SemanticSearchResponse>(apiPath("/semantic-search", {
      q: submittedQuery,
      limit,
    })),
    [submittedQuery, limit]
  );
  const data = results.data;

  return (
    <section className="page">
      <PageHeader
        title="語意搜尋"
        description="以案件 chunk embedding 比對查詢文字，展示命中段落、分數、段落提示與案件來源。"
      />

      <form
        className="semantic-search-form"
        onSubmit={(event) => {
          event.preventDefault();
          setSubmittedQuery(query.trim() || "癌症保險金");
        }}
      >
        <label>
          <span>查詢文字</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="例如：癌症保險金、住院日額、除外責任"
          />
        </label>
        <label>
          <span>回傳筆數</span>
          <select value={limit} onChange={(event) => setLimit(Number(event.target.value))}>
            <option value={5}>5</option>
            <option value={10}>10</option>
            <option value={20}>20</option>
          </select>
        </label>
        <button className="primary-button" type="submit">
          <Search size={17} />
          <span>搜尋</span>
        </button>
      </form>

      <AsyncBlock loading={results.loading} error={results.error}>
        {data && (
          <>
            <div className="metric-grid semantic-metrics">
              <Metric label="Embedding 模型" value={data.embedding_model} />
              <Metric label="候選 chunk" value={data.total_candidates.toLocaleString("zh-TW")} />
              <Metric label="顯示結果" value={`${data.items.length} 筆`} />
              <Metric label="查詢文字" value={data.query} />
            </div>

            <section className="panel">
              <PanelHeader title="分析流程" />
              <div className="semantic-flow">
                <div>
                  <BrainCircuit size={18} />
                  <span>查詢文字轉為本機 CJK hashing vector</span>
                </div>
                <div>
                  <FileText size={18} />
                  <span>與 17254 個案件 chunk embedding 計算 cosine similarity</span>
                </div>
                <div>
                  <Search size={18} />
                  <span>依分數排序後回傳最相近段落與案件來源</span>
                </div>
              </div>
            </section>

            <section className="panel">
              <PanelHeader title="語意搜尋結果" />
              <div className="semantic-results">
                {data.items.map((item, index) => (
                  <article className="semantic-result-card" key={item.chunk_id}>
                    <div className="semantic-result-rank">
                      <strong>#{index + 1}</strong>
                      <span>{formatScore(item.score)}</span>
                    </div>
                    <div className="semantic-result-body">
                      <button type="button" className="link-button" onClick={() => onOpenCase(item.case_id)}>
                        {item.case_number}
                      </button>
                      <div className="semantic-tags">
                        <span>{item.decision_date ?? "無日期"}</span>
                        <span>{item.dispute_type ?? "無爭議類型"}</span>
                        <span>{item.section_hint ?? "未標示段落"}</span>
                        <span>chunk {item.chunk_index}</span>
                      </div>
                      <p>{shortText(item.chunk_text)}</p>
                    </div>
                  </article>
                ))}
                {data.items.length === 0 && (
                  <div className="state-box">目前沒有符合條件的語意搜尋結果。</div>
                )}
              </div>
            </section>
          </>
        )}
      </AsyncBlock>
    </section>
  );
}
