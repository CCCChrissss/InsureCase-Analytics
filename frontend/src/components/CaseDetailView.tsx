import React from "react";
import { BookOpen, ExternalLink, FileText, Landmark, Scale, Users } from "lucide-react";

import { API_BASE } from "../api/client";
import type { CaseDetail, CaseSummaryDetail, SimilarCasesResponse } from "../types";
import { extractLegalReferences } from "../utils/legalReferences";

export function CaseDetailView({
  caseDetail,
  summary,
  summaryError,
  summaryLoading,
  similar,
  similarError,
  similarLoading,
  onOpenCase,
}: {
  caseDetail: CaseDetail;
  summary: CaseSummaryDetail | null;
  summaryError: string | null;
  summaryLoading: boolean;
  similar: SimilarCasesResponse | null;
  similarError: string | null;
  similarLoading: boolean;
  onOpenCase: (caseId: string, label?: string) => void;
}) {
  const [showOriginal, setShowOriginal] = React.useState(false);
  const similarConfidence = getSimilarConfidence(caseDetail, similar);
  const legalReferences = extractLegalReferences(caseDetail.normalized_text || caseDetail.raw_text);
  const decisionResult = resolveDecisionResult(caseDetail.decision_result, summary?.holding);

  React.useEffect(() => {
    setShowOriginal(false);
  }, [caseDetail.case_id]);

  return (
    <article className="case-file">
      <header className="case-file-header">
        <div>
          <span className="case-file-category">{caseDetail.dispute_type || "爭議類型未標示"}</span>
          <h2>{caseDetail.case_number}</h2>
          <div className="case-file-meta">
            <span>決定日期 {caseDetail.decision_date || "未標示"}</span>
            {caseDetail.page_count !== null && <span>{caseDetail.page_count} 頁</span>}
          </div>
        </div>
        <div className="case-file-actions">
          <button className="secondary-button" type="button" onClick={() => setShowOriginal((value) => !value)}>
            {showOriginal ? <FileText size={17} /> : <BookOpen size={17} />}
            {showOriginal ? "返回案件整理" : "查看原文"}
          </button>
          <a
            className="secondary-button"
            href={`${API_BASE}/files/${caseDetail.case_id}/pdf`}
            target="_blank"
            rel="noreferrer"
          >
            <ExternalLink size={17} />
            開啟正式 PDF
          </a>
        </div>
      </header>

      {showOriginal ? (
        <section className="original-document-view">
          <div className="reading-section-heading">
            <BookOpen size={19} />
            <div>
              <h3>案件原文</h3>
              <p>以下為系統抽取文字，頁面與排版請以正式 PDF 為準。</p>
            </div>
          </div>
          <div className="text-viewer original-text-viewer">
            <pre>{caseDetail.normalized_text || caseDetail.raw_text || "此案件沒有可顯示的文字內容。"}</pre>
          </div>
        </section>
      ) : (
        <>
          <section className={`decision-banner ${decisionTone(decisionResult)}`}>
        <span>評議結果</span>
        <strong>{decisionResult}</strong>
          </section>

      <section className="case-reading-section">
        <div className="reading-section-heading">
          <FileText size={19} />
          <div>
            <h3>案件摘要</h3>
            <p>整理案件主張、結論與主要判斷內容。</p>
          </div>
        </div>
        {summaryLoading && <div className="state-box compact">摘要載入中</div>}
        {!summaryLoading && summaryError && <div className="state-box error compact">摘要讀取失敗：{summaryError}</div>}
        {!summaryLoading && !summaryError && !summary && <div className="state-box compact">此案件尚未產生摘要。</div>}
        {!summaryLoading && !summaryError && summary && (
          <div className="claims-summary">
            <SummaryBlock title="評議結論" text={summary.holding} emphasis />
            <div className="claims-summary-columns">
              <SummaryBlock title="申請人主張" text={summary.applicant_claim} />
              <SummaryBlock title="判斷理由" text={summary.reasoning} />
            </div>
          </div>
        )}
      </section>

      <section className="case-reading-section">
        <div className="reading-section-heading">
          <Landmark size={19} />
          <div>
            <h3>法源與契約條款</h3>
            <p>由決定書原文辨識法規與保單條款，提供核對片段。</p>
          </div>
        </div>
        {legalReferences.length > 0 ? (
          <div className="legal-reference-list">
            {legalReferences.map((reference) => (
              <article className="legal-reference" key={reference.id}>
                <div>
                  <span>{reference.category}</span>
                  <strong>{reference.title}</strong>
                </div>
                <p>{reference.excerpt}</p>
              </article>
            ))}
          </div>
        ) : (
          <div className="state-box compact">目前未從原文辨識到明確法規或保單條款。</div>
        )}
        <div className="source-caution">
          <Scale size={16} />
          <span>此區為原文規則擷取，不是法律意見；實際適用內容請以正式評議決定書為準。</span>
        </div>
      </section>

      <section className="case-reading-section">
        <div className="reading-section-heading">
          <Users size={19} />
          <div>
            <h3>相關案件</h3>
            <p>依爭議類型、評議結果與案件關鍵內容整理。</p>
          </div>
        </div>
        {similarLoading && <div className="state-box compact">相關案件載入中</div>}
        {!similarLoading && similarError && <div className="state-box error compact">相關案件讀取失敗：{similarError}</div>}
        {!similarLoading && !similarError && similar && similar.items.length === 0 && (
          <div className="state-box compact">目前沒有找到相關案件。</div>
        )}
        {!similarLoading && !similarError && similar && similar.items.length > 0 && (
          <div className="related-case-list">
            {similarConfidence.isLowConfidence && (
              <div className="low-confidence-note">
                <strong>參考資料有限</strong>
                <span>{similarConfidence.reason}</span>
              </div>
            )}
            {similar.items.map((item) => (
              <button
                key={item.case_id}
                className="related-case-row"
                type="button"
                onClick={() => onOpenCase(item.case_id, item.case_number)}
              >
                <span className="related-case-main">
                  <strong>{item.case_number}</strong>
                  <span>{item.decision_date || "日期未標示"}</span>
                </span>
                <span>{item.dispute_type || "爭議類型未標示"}</span>
                <small>{item.matched_reasons.join("、") || "案件條件相近"}</small>
              </button>
            ))}
          </div>
        )}
          </section>
        </>
      )}
    </article>
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
      reason: "目前結果沒有相同爭議類型，可能是同類型案件數較少，請回到原文判斷。",
    };
  }

  if (topScore <= 20) {
    return {
      isLowConfidence: true,
      reason: "目前僅找到少量共同條件，相關案件僅供初步查找參考。",
    };
  }

  return { isLowConfidence: false, reason: "" };
}

function decisionTone(value: string | null) {
  if (!value) return "neutral";
  if (/無理由|駁回|不受理/.test(value)) return "adverse";
  if (/有理由|應給付|成立/.test(value)) return "favorable";
  return "neutral";
}

function resolveDecisionResult(value: string | null, holding: string | null | undefined) {
  if (holding?.trim()) return holding.trim();
  if (value?.trim() && value.trim() !== "全部") return value.trim();
  return "請參閱案件摘要與正式評議決定書。";
}

function SummaryBlock({ title, text, emphasis = false }: { title: string; text: string | null; emphasis?: boolean }) {
  const safeText = text?.trim() || "未擷取到對應內容。";
  const isLong = safeText.length > 420;

  return (
    <article className={emphasis ? "claim-summary-block emphasis" : "claim-summary-block"}>
      <h4>{title}</h4>
      <p>{isLong ? `${safeText.slice(0, 420)}...` : safeText}</p>
      {isLong && (
        <details>
          <summary>展開完整內容</summary>
          <p>{safeText}</p>
        </details>
      )}
    </article>
  );
}
