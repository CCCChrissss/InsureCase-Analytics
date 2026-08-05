import React from "react";
import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Database,
  FileText,
  FlaskConical,
  Lightbulb,
  Search,
  Sigma,
} from "lucide-react";

import { apiGet, apiPath } from "../api/client";
import { AsyncBlock, Metric, PageHeader, PanelHeader } from "../components/ui";
import { useAsyncData } from "../hooks/useAsyncData";
import type { EmbeddingStatusResponse, QuerySuggestionResponse, SemanticSearchResponse } from "../types";

type SemanticModelMode = "local" | "local_bge_trial";

const LOCAL_MODEL = {
  mode: "local" as const,
  label: "Local Hashing MVP",
  provider: "local",
  model: "local_hashing_cjk_v1",
  dims: 384,
  candidates: 17254,
};

const LOCAL_BGE_TRIAL_MODEL = {
  mode: "local_bge_trial" as const,
  label: "Local BGE Trial",
  provider: "local_bge",
  model: "BAAI/bge-large-zh-v1.5-local",
  dims: 1024,
  candidates: 17254,
};

function formatScore(score: number) {
  return score.toFixed(4);
}

function shortText(value: string, maxLength = 420) {
  return value.length > maxLength ? `${value.slice(0, maxLength)}...` : value;
}

function scorePercent(score: number) {
  return `${Math.round(Math.max(0, Math.min(1, score)) * 100)}%`;
}

export function SemanticSearchPage({ onOpenCase }: { onOpenCase: (caseId: string) => void }) {
  const [query, setQuery] = React.useState("除外責任");
  const [sourceQuery, setSourceQuery] = React.useState("除外責任");
  const [submittedQuery, setSubmittedQuery] = React.useState("除外責任");
  const [limit, setLimit] = React.useState(10);
  const [modelMode, setModelMode] = React.useState<SemanticModelMode>("local");
  const selectedModel = modelMode === "local" ? LOCAL_MODEL : LOCAL_BGE_TRIAL_MODEL;
  const isLocalMode = modelMode === "local";
  const embeddingStatus = useAsyncData(
    () => apiGet<EmbeddingStatusResponse>(apiPath("/embedding-status")),
    []
  );
  const selectedInventory = embeddingStatus.data?.models.find(
    (item) => item.embedding_model === selectedModel.model
  );
  const results = useAsyncData(
    () =>
      apiGet<SemanticSearchResponse>(
        apiPath("/semantic-search", {
          q: submittedQuery,
          limit,
          embedding_provider: selectedModel.provider,
          embedding_model: selectedModel.model,
        })
      ),
    [submittedQuery, limit, modelMode]
  );
  const suggestions = useAsyncData(
    () =>
      isLocalMode
        ? apiGet<QuerySuggestionResponse>(apiPath("/query-suggestions", { q: sourceQuery }))
        : Promise.resolve<QuerySuggestionResponse | null>(null),
    [sourceQuery, isLocalMode]
  );
  const data = results.data;
  const suggestion =
    !suggestions.loading && suggestions.data?.original_query === sourceQuery
      ? suggestions.data
      : null;
  const hasSuggestion = Boolean(suggestion?.available && suggestion.suggested_query);

  return (
    <section className="page">
      <PageHeader
        title="語意搜尋"
        description="以案件段落 chunk embedding 計算相似度，展示查詢詞、模型、候選資料量與命中片段。"
      />

      <section className="panel">
        <PanelHeader title="模型狀態" />
        <div className="model-status-grid">
          <button
            type="button"
            className={`model-option ${modelMode === "local" ? "active" : ""}`}
            onClick={() => setModelMode("local")}
          >
            <Database size={20} />
            <strong>Local MVP</strong>
            <span>本機 hashing baseline，可查詢目前 API 所連資料庫中的 embeddings。</span>
          </button>
          <button
            type="button"
            className={`model-option trial ${modelMode === "local_bge_trial" ? "active" : ""}`}
            onClick={() => setModelMode("local_bge_trial")}
          >
            <FlaskConical size={20} />
            <strong>Local BGE Trial</strong>
            <span>已完成 17254 筆本機 BGE embeddings，可透過 trial backend 實際查詢。</span>
          </button>
        </div>
        <div className="model-status-panel">
          <div>
            <CheckCircle2 size={18} />
            <span>
              目前選擇：{selectedModel.label} / {selectedModel.model} / {selectedModel.dims} 維
            </span>
          </div>
          <div>
            <Database size={18} />
            <span>
              API 資料庫：{embeddingStatus.data?.database_name ?? "讀取中"} / 模型 embeddings：
              {selectedInventory?.embedding_count.toLocaleString("zh-TW") ?? "未提供"}
            </span>
          </div>
          <div className={isLocalMode ? "" : "semantic-warning"}>
            <AlertTriangle size={18} />
            <span>
              {isLocalMode
                ? "此模式會查詢目前 API 所連的 SQLite DB。搜尋品質是本機 hashing MVP，適合展示流程，不等同正式 AI 語意模型。"
                : "此模式會呼叫目前 API；只有 API 以 Local BGE trial DB 啟動時才有結果，全程不呼叫外部 embedding API。"}
            </span>
          </div>
        </div>
      </section>

      {(
        <>
          <form
            className="semantic-search-form"
            onSubmit={(event) => {
              event.preventDefault();
              const nextQuery = query.trim() || "除外責任";
              setSourceQuery(nextQuery);
              setSubmittedQuery(nextQuery);
            }}
          >
            <label>
              <span>查詢詞</span>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="例如：除外責任、必要性醫療、癌症、住院"
              />
            </label>
            <label>
              <span>結果筆數</span>
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

          {suggestions.error && (
            <div className="query-suggestion-error">
              查詢建議暫時無法載入，目前仍使用原查詢。
            </div>
          )}

          {hasSuggestion && suggestion?.suggested_query && (
            <section className="query-suggestion-panel" aria-label="查詢建議">
              <div className="query-suggestion-heading">
                <Lightbulb size={19} />
                <div>
                  <strong>查詢建議</strong>
                  <span>{suggestion.explanation}</span>
                </div>
              </div>
              <div className="query-suggestion-options" role="group" aria-label="選擇實際搜尋查詢">
                <button
                  type="button"
                  className={submittedQuery === sourceQuery ? "active" : ""}
                  aria-pressed={submittedQuery === sourceQuery}
                  onClick={() => setSubmittedQuery(sourceQuery)}
                >
                  <span>原查詢</span>
                  <strong>{sourceQuery}</strong>
                </button>
                <button
                  type="button"
                  className={submittedQuery === suggestion.suggested_query ? "active" : ""}
                  aria-pressed={submittedQuery === suggestion.suggested_query}
                  onClick={() => setSubmittedQuery(suggestion.suggested_query ?? sourceQuery)}
                >
                  <span>建議查詢</span>
                  <strong>{suggestion.suggested_query}</strong>
                </button>
              </div>
              <div className="query-suggestion-current">
                <span>目前執行</span>
                <strong>{submittedQuery}</strong>
                <code>{suggestion.rule_id}</code>
              </div>
            </section>
          )}

          <AsyncBlock loading={results.loading} error={results.error}>
            {data && (
              <>
                <div className="metric-grid semantic-metrics">
                  <Metric label="Embedding 模型" value={data.embedding_model} />
                  <Metric label="Provider / 裝置" value={`${data.embedding_provider} / ${data.embedding_device}`} />
                  <Metric label="向量維度" value={data.embedding_dims.toLocaleString("zh-TW")} />
                  <Metric label="API 耗時" value={`${data.elapsed_ms.toLocaleString("zh-TW")} ms`} />
                  <Metric label="候選 chunks" value={data.total_candidates.toLocaleString("zh-TW")} />
                  <Metric label="顯示結果" value={`${data.items.length} 筆`} />
                  <Metric label="查詢詞" value={data.query} />
                </div>

                <section className="panel">
                  <PanelHeader title="分析流程" />
                  <div className="semantic-flow">
                    <div>
                      <BrainCircuit size={18} />
                      <span>
                        {isLocalMode
                          ? "查詢詞會被轉成本機 CJK n-gram hashing vector。"
                          : "查詢詞會由本機 BGE 模型轉為 1024 維語意向量。"}
                      </span>
                    </div>
                    <div>
                      <FileText size={18} />
                      <span>
                        系統將查詢向量與 {data.total_candidates.toLocaleString("zh-TW")} 個 chunk embeddings 計算
                        cosine similarity。
                      </span>
                    </div>
                    <div>
                      <Sigma size={18} />
                      <span>結果會依相似度排序，並顯示分數、section hint、chunk index 與命中文字段。</span>
                    </div>
                    <div className="semantic-warning">
                      <AlertTriangle size={18} />
                      <span>
                        {isLocalMode
                          ? "這是本機 hashing baseline，適合比較流程，不等同正式 AI 語意品質。"
                          : "Local BGE POC 的 AI 輔助 Strict / Lenient P@5 為 0.9200 / 0.9733；正式 DB 尚未切換，且尚非獨立人工驗證。"}
                      </span>
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
                          <div className="score-meter" aria-label={`相似度 ${formatScore(item.score)}`}>
                            <div style={{ width: scorePercent(item.score) }} />
                          </div>
                        </div>
                        <div className="semantic-result-body">
                          <button type="button" className="link-button" onClick={() => onOpenCase(item.case_id)}>
                            {item.case_number}
                          </button>
                          <div className="semantic-tags">
                            <span>{item.decision_date ?? "無日期"}</span>
                            <span>{item.dispute_type ?? "未分類"}</span>
                            <span>{item.section_hint ?? "未標示段落"}</span>
                            <span>chunk {item.chunk_index}</span>
                            <span>cosine {formatScore(item.score)}</span>
                          </div>
                          <div className="semantic-evidence-label">命中片段</div>
                          <p>{shortText(item.chunk_text)}</p>
                        </div>
                      </article>
                    ))}
                    {data.items.length === 0 && <div className="state-box">目前沒有符合條件的語意搜尋結果。</div>}
                  </div>
                </section>
              </>
            )}
          </AsyncBlock>
        </>
      )}
    </section>
  );
}
