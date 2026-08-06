import React from "react";
import {
  BookOpen,
  CheckCircle2,
  ClipboardCheck,
  ChevronDown,
  ChevronUp,
  ChevronsDown,
  ChevronsUp,
  ExternalLink,
  FileText,
  Info,
  Landmark,
  Scale,
  TriangleAlert,
  Users,
} from "lucide-react";

import { API_BASE } from "../api/client";
import type {
  AiCaseSummaryResponse,
  CaseDetail,
  CaseDocumentSections,
  DocumentSection,
  SemanticSimilarCasesResponse,
} from "../types";
import { selectCompleteCaseText, type CaseTextMode } from "../utils/caseText";
import { extractLegalReferences } from "../utils/legalReferences";

const DEFAULT_EXPANDED_SECTION_TYPES = new Set(["holding", "issues"]);

export function CaseDetailView({
  caseDetail,
  aiSummary,
  aiSummaryError,
  aiSummaryLoading,
  documentSections,
  documentError,
  documentLoading,
  similar,
  similarError,
  similarLoading,
  onOpenCase,
}: {
  caseDetail: CaseDetail;
  aiSummary: AiCaseSummaryResponse | null;
  aiSummaryError: string | null;
  aiSummaryLoading: boolean;
  documentSections: CaseDocumentSections | null;
  documentError: string | null;
  documentLoading: boolean;
  similar: SemanticSimilarCasesResponse | null;
  similarError: string | null;
  similarLoading: boolean;
  onOpenCase: (caseId: string, label?: string) => void;
}) {
  const [showOriginal, setShowOriginal] = React.useState(false);
  const [textMode, setTextMode] = React.useState<CaseTextMode>("normalized");
  const [expandedSectionTypes, setExpandedSectionTypes] = React.useState<Set<string>>(
    () => new Set(DEFAULT_EXPANDED_SECTION_TYPES)
  );
  const articleRef = React.useRef<HTMLElement>(null);
  const similarConfidence = getSimilarConfidence(similar);
  const legalReferences = extractLegalReferences(caseDetail.normalized_text || caseDetail.raw_text);
  const holdingSection = documentSections?.sections.find((section) => section.section_type === "holding");
  const decisionResult = resolveDecisionResult(caseDetail.decision_result, holdingSection);
  const completeText = selectCompleteCaseText(
    {
      normalizedText: caseDetail.normalized_text,
      rawText: caseDetail.raw_text,
      normalizedTextChars: caseDetail.normalized_text_chars,
      rawTextChars: caseDetail.raw_text_chars,
    },
    textMode
  );
  const allSectionsExpanded = Boolean(
    documentSections?.sections.length &&
      documentSections.sections.every((section) => expandedSectionTypes.has(section.section_type))
  );

  React.useEffect(() => {
    setShowOriginal(false);
    setTextMode("normalized");
    setExpandedSectionTypes(new Set(DEFAULT_EXPANDED_SECTION_TYPES));
  }, [caseDetail.case_id]);

  React.useEffect(() => {
    // Changing the document mode must reset the outer reader, otherwise a prior
    // scroll position can make a complete document look as though its beginning is missing.
    articleRef.current?.closest<HTMLElement>(".case-workspace-content")?.scrollTo({ top: 0 });
  }, [showOriginal, textMode]);

  const toggleSection = (sectionType: string) => {
    setExpandedSectionTypes((current) => {
      const next = new Set(current);
      if (next.has(sectionType)) next.delete(sectionType);
      else next.add(sectionType);
      return next;
    });
  };

  const toggleAllSections = () => {
    if (!documentSections) return;
    setExpandedSectionTypes(
      allSectionsExpanded
        ? new Set()
        : new Set(documentSections.sections.map((section) => section.section_type))
    );
  };

  return (
    <article className="case-file" ref={articleRef}>
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
            {showOriginal ? "返回案件整理" : "查看逐字全文"}
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
        <OriginalDocumentView
          completeText={completeText}
          textMode={textMode}
          onTextModeChange={setTextMode}
        />
      ) : (
        <>
          <section className={`decision-banner ${decisionTone(decisionResult)}`}>
            <span>評議結果</span>
            <strong>{decisionResult}</strong>
          </section>

          <AiSummarySection
            response={aiSummary}
            error={aiSummaryError}
            loading={aiSummaryLoading}
          />

          <section className="case-reading-section">
            <div className="reading-section-heading">
              <FileText size={19} />
              <div>
                <h3>完整案件內容</h3>
                <p>依評議決定書原文分段呈現，未做摘要或字數截斷。</p>
              </div>
            </div>

            {documentLoading && <div className="state-box compact">案件內容載入中</div>}
            {!documentLoading && documentError && (
              <div className="state-box error compact">案件內容讀取失敗：{documentError}</div>
            )}
            {!documentLoading && !documentError && documentSections && (
              <>
                <div className="document-section-toolbar">
                  <div className={documentSections.complete_coverage ? "document-coverage" : "document-coverage mismatch"}>
                    {documentSections.complete_coverage ? <CheckCircle2 size={18} /> : <TriangleAlert size={18} />}
                    <div>
                      <strong>
                        {documentSections.complete_coverage ? "原文已完整分段" : "原文分段核對異常"}
                      </strong>
                      <span>
                        涵蓋 {formatCharacterCount(documentSections.covered_chars)} / {formatCharacterCount(documentSections.source_chars)} 字
                      </span>
                    </div>
                  </div>
                  <button className="secondary-button" type="button" onClick={toggleAllSections}>
                    {allSectionsExpanded ? <ChevronsUp size={17} /> : <ChevronsDown size={17} />}
                    {allSectionsExpanded ? "全部收合" : "全部展開"}
                  </button>
                </div>
                <div className="document-section-list">
                  {documentSections.sections.map((section) => {
                    const expanded = expandedSectionTypes.has(section.section_type);
                    const panelId = `document-panel-${caseDetail.case_id}-${section.section_id}`;
                    return (
                      <article className={expanded ? "document-section-item expanded" : "document-section-item"} key={section.section_id}>
                        <button
                          className="document-section-toggle"
                          type="button"
                          aria-expanded={expanded}
                          aria-controls={panelId}
                          onClick={() => toggleSection(section.section_type)}
                        >
                          <span>
                            <strong>{section.title}</strong>
                            <small>{formatCharacterCount(section.char_count)} 字</small>
                          </span>
                          {expanded ? <ChevronUp size={19} /> : <ChevronDown size={19} />}
                        </button>
                        {expanded && (
                          <div className="document-section-content" id={panelId}>
                            {/* Content is the exact backend source slice, including its original heading. */}
                            <pre>{section.content}</pre>
                          </div>
                        )}
                      </article>
                    );
                  })}
                </div>
                <div className="source-caution">
                  <Info size={16} />
                  <span>區塊標題由系統辨識；每一區仍保留完整原文，可用逐字全文及正式 PDF 交叉核對。</span>
                </div>
              </>
            )}
          </section>

          {/* This area intentionally lists statutes only; policy terms remain in the case text. */}
          <section className="case-reading-section">
            <div className="reading-section-heading">
              <Landmark size={19} />
              <div>
                <h3>法源依據</h3>
                <p>僅列出決定書明確引用的法規條文，不顯示個別保單或契約條款。</p>
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
                  </article>
                ))}
              </div>
            ) : (
              <div className="state-box compact">目前未從原文辨識到明確法規條文。</div>
            )}
            <div className="source-caution">
              <Scale size={16} />
              <span>此區僅整理法規引用，不是法律意見；實際適用內容請以正式評議決定書與現行法規為準。</span>
            </div>
          </section>

          <RelatedCasesSection
            similar={similar}
            similarError={similarError}
            similarLoading={similarLoading}
            similarConfidence={similarConfidence}
            onOpenCase={onOpenCase}
          />
        </>
      )}
    </article>
  );
}

function AiSummarySection({
  response,
  error,
  loading,
}: {
  response: AiCaseSummaryResponse | null;
  error: string | null;
  loading: boolean;
}) {
  const item = response?.item ?? null;
  const summary = item?.summary;
  const statusLabel = item?.official ? "已人工確認" : "AI 產生，尚未人工確認";

  return (
    <section className="case-reading-section ai-case-summary">
      <div className="ai-summary-heading">
        <div className="reading-section-heading">
          <ClipboardCheck size={19} />
          <div>
            <h3>案件摘要</h3>
            <p>整理雙方主張、爭點、判斷理由與結果，重要內容仍應回查原文。</p>
          </div>
        </div>
        {item && (
          <span className={item.official ? "review-status approved" : "review-status unreviewed"}>
            {item.official && <CheckCircle2 size={15} />}
            {statusLabel}
          </span>
        )}
      </div>

      {loading && <div className="state-box compact">案件摘要載入中</div>}
      {!loading && error && (
        <div className="state-box error compact" title={error}>案件摘要目前無法使用，請直接查看完整案件內容。</div>
      )}
      {!loading && !error && !response?.available && (
        <div className="state-box compact">此案件尚未建立經來源核對的摘要。</div>
      )}
      {!loading && !error && summary && item && (
        <>
          {/* Unreviewed POC output stays inspectable, but cannot be mistaken for a human decision. */}
          {!item.official && (
            <div className="ai-summary-warning">
              <TriangleAlert size={17} />
              <span>此摘要尚未經人工確認，只能作為閱讀方向，不可取代評議決定書原文。</span>
            </div>
          )}
          <div className="ai-summary-grid">
            <SummaryTextBlock title="案件背景" value={summary.background} />
            <SummaryTextBlock title="申請人主張" value={summary.applicant_position} />
            <SummaryTextBlock title="相對人主張" value={summary.respondent_position} />
            <SummaryListBlock title="本件爭點" items={summary.core_issues} />
            <SummaryListBlock title="判斷理由" items={summary.reasoning_points} wide />
            <SummaryTextBlock title="摘要結果" value={summary.decision_result} wide />
          </div>
          {summary.evidence.length > 0 && (
            <details className="summary-evidence">
              <summary>查看摘要引用原文（{summary.evidence.length} 則）</summary>
              <div className="summary-evidence-list">
                {summary.evidence.map((evidence, index) => (
                  <article key={`${evidence.category}-${evidence.section_title}-${index}`}>
                    <span>{evidence.section_title || evidenceCategoryLabel(evidence.category)}</span>
                    <p>{evidence.evidence_quote}</p>
                  </article>
                ))}
              </div>
            </details>
          )}
          <div className="source-caution">
            <Info size={16} />
            <span>摘要內容附有原文引用，可展開核對；正式判斷仍以完整評議決定書為準。</span>
          </div>
        </>
      )}
    </section>
  );
}

function SummaryTextBlock({ title, value, wide = false }: { title: string; value: string; wide?: boolean }) {
  return (
    <article className={wide ? "ai-summary-block wide" : "ai-summary-block"}>
      <h4>{title}</h4>
      <p>{value}</p>
    </article>
  );
}

function SummaryListBlock({ title, items, wide = false }: { title: string; items: string[]; wide?: boolean }) {
  return (
    <article className={wide ? "ai-summary-block wide" : "ai-summary-block"}>
      <h4>{title}</h4>
      {items.length > 0 ? (
        <ol>
          {items.map((item, index) => <li key={`${title}-${index}`}>{item}</li>)}
        </ol>
      ) : (
        <p>目前沒有可顯示的內容。</p>
      )}
    </article>
  );
}

function evidenceCategoryLabel(category: string) {
  const labels: Record<string, string> = {
    background: "案件背景",
    applicant_position: "申請人主張",
    respondent_position: "相對人主張",
    core_issue: "本件爭點",
    reasoning: "判斷理由",
    decision_result: "評議結果",
  };
  return labels[category] || "原文依據";
}

function OriginalDocumentView({
  completeText,
  textMode,
  onTextModeChange,
}: {
  completeText: ReturnType<typeof selectCompleteCaseText>;
  textMode: CaseTextMode;
  onTextModeChange: (mode: CaseTextMode) => void;
}) {
  return (
    <section className="original-document-view">
      <div className="reading-section-heading">
        <BookOpen size={19} />
        <div>
          <h3>完整案件文字</h3>
          <p>不做字數截斷；可核對整理文字、原始抽取文字與正式 PDF。</p>
        </div>
      </div>
      <div className="original-document-toolbar">
        <div className="text-source-switch" role="group" aria-label="案件文字來源">
          <button
            className={textMode === "normalized" ? "active" : ""}
            type="button"
            onClick={() => onTextModeChange("normalized")}
            aria-pressed={textMode === "normalized"}
          >
            整理文字
          </button>
          <button
            className={textMode === "raw" ? "active" : ""}
            type="button"
            onClick={() => onTextModeChange("raw")}
            aria-pressed={textMode === "raw"}
          >
            原始抽取文字
          </button>
        </div>
        <div className={`text-integrity ${completeText.matchesExpected === false ? "mismatch" : ""}`}>
          {completeText.matchesExpected === false ? <TriangleAlert size={17} /> : <CheckCircle2 size={17} />}
          <div>
            <strong>已載入 {formatCharacterCount(completeText.actualChars)} 字</strong>
            <span>{textIntegrityDescription(completeText.expectedChars, completeText.matchesExpected)}</span>
          </div>
        </div>
      </div>
      {completeText.usedFallback && (
        <div className="source-caution">
          <Info size={16} />
          <span>所選文字來源不存在，已改為顯示另一份可用文字。</span>
        </div>
      )}
      <div className="text-viewer original-text-viewer">
        <pre>{completeText.text || "此案件沒有可顯示的文字內容。"}</pre>
      </div>
      <div className="source-caution">
        <Scale size={16} />
        <span>文字版可能受 PDF 抽取品質影響；頁碼、表格及正式內容仍以評議決定書 PDF 為準。</span>
      </div>
    </section>
  );
}

function RelatedCasesSection({
  similar,
  similarError,
  similarLoading,
  similarConfidence,
  onOpenCase,
}: {
  similar: SemanticSimilarCasesResponse | null;
  similarError: string | null;
  similarLoading: boolean;
  similarConfidence: ReturnType<typeof getSimilarConfidence>;
  onOpenCase: (caseId: string, label?: string) => void;
}) {
  return (
    <section className="case-reading-section">
      <div className="reading-section-heading">
        <Users size={19} />
        <div>
          <h3>相關案件</h3>
          <p>依案件內容的語意相近程度排列。</p>
        </div>
      </div>
      {similarLoading && <div className="state-box compact">相關案件載入中</div>}
      {!similarLoading && similarError && (
        <div className="state-box error compact" title={similarError}>語意相似案件目前無法使用，請稍後再試。</div>
      )}
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
              <span className="related-case-meta">
                <span>{item.dispute_type || "爭議類型未標示"}</span>
                <strong className="similarity-value">相似度 {formatSimilarity(item.score)}</strong>
              </span>
              <small>{semanticReason(item.matched_chunks[0]?.section_hint)}</small>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function getSimilarConfidence(similar: SemanticSimilarCasesResponse | null) {
  if (!similar || similar.items.length === 0) return { isLowConfidence: false, reason: "" };
  if ((similar.items[0]?.score ?? 0) < 0.45) {
    return {
      isLowConfidence: true,
      reason: "目前僅找到少量共同條件，相關案件僅供初步查找參考。",
    };
  }
  return { isLowConfidence: false, reason: "" };
}

function formatSimilarity(score: number) {
  return `${Math.round(Math.min(Math.max(score, 0), 1) * 100)}%`;
}

function semanticReason(sectionHint: string | null | undefined) {
  return sectionHint ? `主要相近內容：${sectionHint}` : "案件內容語意相近";
}

function decisionTone(value: string | null) {
  if (!value) return "neutral";
  if (/無理由|駁回|不受理/.test(value)) return "adverse";
  if (/有理由|應給付|成立/.test(value)) return "favorable";
  return "neutral";
}

function resolveDecisionResult(value: string | null, holding: DocumentSection | undefined) {
  if (holding?.content.trim()) {
    const headingIndex = holding.heading ? holding.content.indexOf(holding.heading) : -1;
    const body = headingIndex >= 0
      ? holding.content.slice(headingIndex + (holding.heading?.length ?? 0)).trim()
      : holding.content.trim();
    if (body) return body;
  }
  if (value?.trim() && value.trim() !== "全部") return value.trim();
  return "請參閱完整案件內容與正式評議決定書。";
}

function formatCharacterCount(value: number): string {
  return new Intl.NumberFormat("zh-TW").format(value);
}

function textIntegrityDescription(expectedChars: number | null, matchesExpected: boolean | null): string {
  if (expectedChars === null || matchesExpected === null) return "資料庫沒有可供比對的記錄字數";
  if (!matchesExpected) return `與資料庫記錄 ${formatCharacterCount(expectedChars)} 字不一致，請以 PDF 為準`;
  return `與資料庫記錄 ${formatCharacterCount(expectedChars)} 字一致`;
}
