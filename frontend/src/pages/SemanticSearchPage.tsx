import React from "react";
import {
  AlertTriangle,
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  Database,
  FileText,
  FlaskConical,
  Search,
  Sigma,
} from "lucide-react";

import { apiGet, apiPath } from "../api/client";
import { AsyncBlock, Metric, PageHeader, PanelHeader } from "../components/ui";
import { useAsyncData } from "../hooks/useAsyncData";
import type { SemanticSearchResponse } from "../types";

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
  candidates: 1000,
};

const TRIAL_QUERY_SUMMARY = [
  { query: "除外責任", top1: "除外責任", note: "Top 5 中 4 筆為除外責任，結果集中。" },
  { query: "必要性醫療", top1: "必要性醫療", note: "Top 5 全部為必要性醫療，穩定度最高。" },
  { query: "癌症", top1: "停效期間事故認定", note: "有命中癌症類型，也會跨到疾病事實相關爭點。" },
  { query: "住院", top1: "必要性醫療", note: "多數結果落在醫療必要性與承保範圍。" },
  { query: "失能", top1: "投保時已患疾病或在妊娠中", note: "語意相關但類型分散，需要回看 chunk 原文。" },
];

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
  const [submittedQuery, setSubmittedQuery] = React.useState("除外責任");
  const [limit, setLimit] = React.useState(10);
  const [modelMode, setModelMode] = React.useState<SemanticModelMode>("local");
  const selectedModel = modelMode === "local" ? LOCAL_MODEL : LOCAL_BGE_TRIAL_MODEL;
  const isLocalMode = modelMode === "local";
  const results = useAsyncData(
    () =>
      isLocalMode
        ? apiGet<SemanticSearchResponse>(
            apiPath("/semantic-search", {
              q: submittedQuery,
              limit,
              embedding_provider: LOCAL_MODEL.provider,
              embedding_model: LOCAL_MODEL.model,
            })
          )
        : Promise.resolve<SemanticSearchResponse | null>(null),
    [submittedQuery, limit, isLocalMode]
  );
  const data = results.data;

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
            <span>正式 DB 目前使用的模型，可直接查詢 17254 個 chunks。</span>
          </button>
          <button
            type="button"
            className={`model-option trial ${modelMode === "local_bge_trial" ? "active" : ""}`}
            onClick={() => setModelMode("local_bge_trial")}
          >
            <FlaskConical size={20} />
            <strong>Local BGE Trial</strong>
            <span>已在 RTX 4050 完成 1000 筆離線試測，但正式 DB 尚未切換。</span>
          </button>
        </div>
        <div className="model-status-panel">
          <div>
            <CheckCircle2 size={18} />
            <span>
              目前選擇：{selectedModel.label} / {selectedModel.model} / {selectedModel.dims} 維
            </span>
          </div>
          <div className={isLocalMode ? "" : "semantic-warning"}>
            <AlertTriangle size={18} />
            <span>
              {isLocalMode
                ? "此模式會查詢正式 SQLite DB。搜尋品質是本機 hashing MVP，適合展示流程，不等同正式 AI 語意模型。"
                : "此模式目前只展示本機 BGE trial 報告，不會呼叫外部 API，也不會查詢正式 DB 以外的 trial DB。"}
            </span>
          </div>
        </div>
      </section>

      {isLocalMode ? (
        <>
          <form
            className="semantic-search-form"
            onSubmit={(event) => {
              event.preventDefault();
              setSubmittedQuery(query.trim() || "除外責任");
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

          <AsyncBlock loading={results.loading} error={results.error}>
            {data && (
              <>
                <div className="metric-grid semantic-metrics">
                  <Metric label="Embedding 模型" value={data.embedding_model} />
                  <Metric label="候選 chunks" value={data.total_candidates.toLocaleString("zh-TW")} />
                  <Metric label="顯示結果" value={`${data.items.length} 筆`} />
                  <Metric label="查詢詞" value={data.query} />
                </div>

                <section className="panel">
                  <PanelHeader title="分析流程" />
                  <div className="semantic-flow">
                    <div>
                      <BrainCircuit size={18} />
                      <span>查詢詞會被轉成本機 CJK n-gram hashing vector。</span>
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
                      <span>這是本機 hashing MVP，適合展示查詢流程；本機 BGE 的品質仍需完成 75 筆人工 relevance 標註。</span>
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
      ) : (
        <section className="panel">
          <PanelHeader title="Local BGE 1000 筆離線試測摘要" />
          <div className="trial-summary">
            <div className="metric-grid semantic-metrics">
              <Metric label="Provider" value={LOCAL_BGE_TRIAL_MODEL.provider} />
              <Metric label="Embedding 模型" value={LOCAL_BGE_TRIAL_MODEL.model} />
              <Metric label="Trial candidates" value={LOCAL_BGE_TRIAL_MODEL.candidates.toLocaleString("zh-TW")} />
              <Metric label="狀態" value="等待人工標註" />
            </div>
            <div className="semantic-method-note">
              這組結果來自 `docs/local_bge_semantic_query_trial_1000.md`，由本機模型快取與 RTX 4050 產生。正式 DB 尚未全量重建 BGE embeddings，因此前端目前只展示試測摘要。
            </div>
            <div className="trial-summary-table">
              {TRIAL_QUERY_SUMMARY.map((item) => (
                <div key={item.query}>
                  <strong>{item.query}</strong>
                  <span>Top 1：{item.top1}</span>
                  <p>{item.note}</p>
                </div>
              ))}
            </div>
            <div className="semantic-flow">
              <div>
                <BarChart3 size={18} />
                <span>可展示重點：1000 筆 trial 已證明本機 BGE 查詢流程可跑通，全程不使用外部 embedding API。</span>
              </div>
              <div className="semantic-warning">
                <AlertTriangle size={18} />
                <span>限制：這還不是正式 DB 切換；目前需先完成 75 筆人工 relevance 標註，再決定是否全量重建 embeddings。</span>
              </div>
            </div>
          </div>
        </section>
      )}
    </section>
  );
}
