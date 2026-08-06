import React from "react";
import { Minus, X } from "lucide-react";

import { apiGet, apiPath } from "../api/client";
import { LOCAL_BGE_MODEL, LOCAL_BGE_PROVIDER } from "../config/semantic";
import { useAsyncData } from "../hooks/useAsyncData";
import type { OpenCaseTab } from "../hooks/useOpenCases";
import type { CaseDetail, CaseDocumentSections, SemanticSimilarCasesResponse } from "../types";
import { CaseDetailView } from "./CaseDetailView";
import { AsyncBlock } from "./ui";

export function CaseWorkspaceModal({
  tabs,
  activeCaseId,
  onSelect,
  onClose,
  onMinimize,
  onRename,
  onOpenCase,
}: {
  tabs: OpenCaseTab[];
  activeCaseId: string;
  onSelect: (caseId: string) => void;
  onClose: (caseId: string) => void;
  onMinimize: () => void;
  onRename: (caseId: string, label: string) => void;
  onOpenCase: (caseId: string, label?: string) => void;
}) {
  const contentRef = React.useRef<HTMLDivElement>(null);
  const detail = useAsyncData(() => apiGet<CaseDetail>(`/cases/${activeCaseId}`), [activeCaseId]);
  const documentSections = useAsyncData(
    () => apiGet<CaseDocumentSections>(`/cases/${activeCaseId}/document-sections`),
    [activeCaseId]
  );
  const similar = useAsyncData(
    () => apiGet<SemanticSimilarCasesResponse>(apiPath(`/cases/${activeCaseId}/semantic-similar`, {
      limit: 5,
      chunks_per_case: 1,
      embedding_provider: LOCAL_BGE_PROVIDER,
      embedding_model: LOCAL_BGE_MODEL,
    })),
    [activeCaseId]
  );

  React.useEffect(() => {
    if (detail.data?.case_number) onRename(activeCaseId, detail.data.case_number);
  }, [activeCaseId, detail.data?.case_number, onRename]);

  React.useEffect(() => {
    contentRef.current?.scrollTo({ top: 0 });
  }, [activeCaseId]);

  React.useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onMinimize();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onMinimize]);

  return (
    <div className="case-workspace-overlay" role="dialog" aria-modal="true" aria-label="已開啟案件">
      <section className="case-workspace-modal">
        <header className="case-workspace-tabs-bar">
          <div className="case-tabs" role="tablist" aria-label="案件分頁">
            {tabs.map((tab) => (
              <div className={tab.caseId === activeCaseId ? "case-tab active" : "case-tab"} key={tab.caseId}>
                <button
                  className="case-tab-select"
                  type="button"
                  role="tab"
                  aria-selected={tab.caseId === activeCaseId}
                  onClick={() => onSelect(tab.caseId)}
                  title={tab.label}
                >
                  {tab.label}
                </button>
                <button
                  className="case-tab-close"
                  type="button"
                  onClick={() => onClose(tab.caseId)}
                  aria-label={`關閉 ${tab.label}`}
                  title={`關閉 ${tab.label}`}
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
          <button className="workspace-minimize" type="button" onClick={onMinimize} aria-label="收起案件視窗" title="收起案件視窗">
            <Minus size={19} />
          </button>
        </header>

        <div className="case-workspace-content" ref={contentRef}>
          <AsyncBlock loading={detail.loading} error={detail.error}>
            {detail.data && (
              <CaseDetailView
                caseDetail={detail.data}
                documentSections={documentSections.data}
                documentError={documentSections.error}
                documentLoading={documentSections.loading}
                similar={similar.data}
                similarError={similar.error}
                similarLoading={similar.loading}
                onOpenCase={onOpenCase}
              />
            )}
          </AsyncBlock>
        </div>
      </section>
    </div>
  );
}
