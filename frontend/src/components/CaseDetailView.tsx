import { API_BASE } from "../api/client";
import type { CaseDetail, CaseSummaryDetail, SemanticSimilarCasesResponse, SimilarCasesResponse } from "../types";

export function CaseDetailView({
  caseDetail,
  summary,
  summaryError,
  summaryLoading,
  similar,
  similarError,
  similarLoading,
  semanticSimilar,
  semanticSimilarError,
  semanticSimilarLoading,
  onOpenCase
}: {
  caseDetail: CaseDetail;
  summary: CaseSummaryDetail | null;
  summaryError: string | null;
  summaryLoading: boolean;
  similar: SimilarCasesResponse | null;
  similarError: string | null;
  similarLoading: boolean;
  semanticSimilar: SemanticSimilarCasesResponse | null;
  semanticSimilarError: string | null;
  semanticSimilarLoading: boolean;
  onOpenCase: (caseId: string) => void;
}) {
  const similarConfidence = getSimilarConfidence(caseDetail, similar);

  return (
    <div className="case-detail">
      <div className="detail-title">
        <h2>{caseDetail.case_number}</h2>
        <a className="secondary-button" href={`${API_BASE}/files/${caseDetail.case_id}/pdf`} target="_blank" rel="noreferrer">
          開啟 PDF
        </a>
      </div>
      <dl className="detail-grid">
        <div><dt>決定日期</dt><dd>{caseDetail.decision_date}</dd></div>
        <div><dt>爭議類型</dt><dd>{caseDetail.dispute_type}</dd></div>
        <div><dt>評議結果</dt><dd>{caseDetail.decision_result}</dd></div>
        <div><dt>頁數</dt><dd>{caseDetail.page_count}</dd></div>
      </dl>
      <section className="summary-section">
        <div className="summary-header">
          <h3>案件摘要</h3>
          {summary?.summary_method && <span>{summary.summary_method}</span>}
        </div>
        {summaryLoading && <div className="state-box compact">摘要載入中</div>}
        {!summaryLoading && summaryError && <div className="state-box error compact">摘要讀取失敗：{summaryError}</div>}
        {!summaryLoading && !summaryError && !summary && <div className="state-box compact">尚未產生摘要。</div>}
        {!summaryLoading && !summaryError && summary && (
          <div className="summary-grid">
            <SummaryBlock title="主文" text={summary.holding} />
            <SummaryBlock title="申請人主張" text={summary.applicant_claim} />
            <SummaryBlock title="判斷理由" text={summary.reasoning} />
          </div>
        )}
      </section>
      <section className="similar-section">
        <div className="summary-header">
          <h3>相似案件</h3>
          {similar && <span>{similar.total_candidates} 個候選</span>}
        </div>
        {similarLoading && <div className="state-box compact">相似案件載入中</div>}
        {!similarLoading && similarError && <div className="state-box error compact">相似案件讀取失敗：{similarError}</div>}
        {!similarLoading && !similarError && similar && similar.items.length === 0 && (
          <div className="state-box compact">目前沒有找到相似案件。</div>
        )}
        {!similarLoading && !similarError && similar && similar.items.length > 0 && (
          <div className="similar-list">
            {similarConfidence.isLowConfidence && (
              <div className="low-confidence-note">
                <strong>低信心提示</strong>
                <span>{similarConfidence.reason}</span>
              </div>
            )}
            {similar.items.map((item) => (
              <button key={item.case_id} className="similar-row" type="button" onClick={() => onOpenCase(item.case_id)}>
                <span className="case-number">{item.case_number}</span>
                <span className="case-meta">{item.decision_date} · {item.dispute_type} · 分數 {item.score}</span>
                <span className="reason-list">{item.matched_reasons.join(" / ")}</span>
              </button>
            ))}
          </div>
        )}
      </section>
      <section className="similar-section semantic-similar-section">
        <div className="summary-header">
          <h3>語意相似案件</h3>
          {semanticSimilar && <span>{semanticSimilar.embedding_model} · {semanticSimilar.total_candidates} 候選案件</span>}
        </div>
        {semanticSimilarLoading && <div className="state-box compact">語意相似案件載入中</div>}
        {!semanticSimilarLoading && semanticSimilarError && <div className="state-box error compact">語意相似案件讀取失敗：{semanticSimilarError}</div>}
        {!semanticSimilarLoading && !semanticSimilarError && semanticSimilar && semanticSimilar.items.length === 0 && (
          <div className="state-box compact">目前沒有語意相似案件。</div>
        )}
        {!semanticSimilarLoading && !semanticSimilarError && semanticSimilar && semanticSimilar.items.length > 0 && (
          <div className="semantic-case-list">
            <div className="semantic-method-note">
              以來源案件 {semanticSimilar.source_chunk_count} 個 chunk 建立案件向量，再比對所有候選案件 chunk；目前模型為本機 MVP，非正式 AI embedding。
            </div>
            {semanticSimilar.items.map((item) => (
              <article className="semantic-case-card" key={item.case_id}>
                <div className="semantic-case-head">
                  <button className="link-button" type="button" onClick={() => onOpenCase(item.case_id)}>
                    {item.case_number}
                  </button>
                  <strong>{item.score.toFixed(4)}</strong>
                </div>
                <div className="semantic-tags">
                  <span>{item.decision_date ?? "無日期"}</span>
                  <span>{item.dispute_type ?? "無爭議類型"}</span>
                </div>
                <div className="semantic-match-list">
                  {item.matched_chunks.map((chunk) => (
                    <div className="semantic-match" key={chunk.chunk_id}>
                      <span>{chunk.section_hint ?? "未標示段落"} · chunk {chunk.chunk_index} · {chunk.score.toFixed(4)}</span>
                      <p>{shortText(chunk.chunk_text)}</p>
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
      <div className="text-viewer">
        <pre>{caseDetail.normalized_text}</pre>
      </div>
    </div>
  );
}

function getSimilarConfidence(caseDetail: CaseDetail, similar: SimilarCasesResponse | null) {
  if (!similar || similar.items.length === 0) {
    return { isLowConfidence: false, reason: "" };
  }

  const sourceDisputeType = caseDetail.dispute_type;
  const sameDisputeTypeCount = sourceDisputeType
    ? similar.items.filter((item) => item.dispute_type === sourceDisputeType).length
    : 0;
  const topScore = similar.items[0]?.score ?? 0;

  if (sameDisputeTypeCount === 0) {
    return {
      isLowConfidence: true,
      reason: "Top 5 相似案件沒有同爭議類型，通常代表此爭議類型案件數不足，結果僅供參考。"
    };
  }

  if (topScore <= 20) {
    return {
      isLowConfidence: true,
      reason: "最高相似分數偏低，主要只命中評議結果或決定類別，尚未形成穩定相似關係。"
    };
  }

  return { isLowConfidence: false, reason: "" };
}

function shortText(value: string, maxLength = 220) {
  return value.length > maxLength ? `${value.slice(0, maxLength)}...` : value;
}

function SummaryBlock({ title, text }: { title: string; text: string | null }) {
  return (
    <article className="summary-block">
      <h4>{title}</h4>
      <p>{text || "未擷取到對應段落。"}</p>
    </article>
  );
}
