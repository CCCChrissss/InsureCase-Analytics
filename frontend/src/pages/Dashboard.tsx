import React from "react";
import { BrainCircuit, FileSearch, ListFilter, ShieldCheck } from "lucide-react";

import { apiGet } from "../api/client";
import { AsyncBlock, Metric, PageHeader, PanelHeader } from "../components/ui";
import { useAsyncData } from "../hooks/useAsyncData";
import type { OverviewStatistics } from "../types";

type DashboardProps = {
  onOpenCases: () => void;
  onOpenSearch: () => void;
  onOpenSemanticSearch: () => void;
  onOpenQuality: () => void;
};

const searchWorkflows = [
  {
    title: "依案號與分類查找",
    description: "用年度、爭議類型、案號縮小範圍，適合已知道案件線索時使用。",
    action: "開啟案件查找",
    icon: <ListFilter size={20} />,
    key: "cases",
  },
  {
    title: "全文關鍵字搜尋",
    description: "搜尋 normalized text，查看命中的案件與文字片段，適合找特定疾病、條款或理賠關鍵字。",
    action: "開啟全文搜尋",
    icon: <FileSearch size={20} />,
    key: "search",
  },
  {
    title: "語意相似查找",
    description: "以 chunk embedding 找相近段落，並展示分數、段落提示與案件來源。",
    action: "開啟語意搜尋",
    icon: <BrainCircuit size={20} />,
    key: "semantic",
  },
];

export function Dashboard({
  onOpenCases,
  onOpenSearch,
  onOpenSemanticSearch,
  onOpenQuality,
}: DashboardProps) {
  const overview = useAsyncData(() => apiGet<OverviewStatistics>("/statistics/overview"), []);
  const dateRange = overview.data?.first_decision_date && overview.data.last_decision_date
    ? `${overview.data.first_decision_date} - ${overview.data.last_decision_date}`
    : "尚無日期資料";
  const yearRange = overview.data?.roc_years.length
    ? overview.data.roc_years.map((year) => `ROC ${year}`).join(" / ")
    : "尚無年度資料";

  const openWorkflow = (key: string) => {
    if (key === "cases") onOpenCases();
    if (key === "search") onOpenSearch();
    if (key === "semantic") onOpenSemanticSearch();
  };

  return (
    <section className="page">
      <PageHeader
        title="案件查找工作台"
        description="以案件查找、全文搜尋與語意搜尋為主，快速定位人壽保險評議決定書與相似段落。"
        action={
          <div className="header-actions">
            <button className="secondary-button" type="button" onClick={onOpenQuality}>
              查看分析驗證
            </button>
            <button className="primary-button" type="button" onClick={onOpenSearch}>
              開始搜尋
            </button>
          </div>
        }
      />

      <AsyncBlock loading={overview.loading} error={overview.error}>
        {overview.data && (
          <div className="metric-grid">
            <Metric label="可查案件" value={overview.data.case_count.toLocaleString()} />
            <Metric label="年度範圍" value={yearRange} />
            <Metric label="爭議類型" value={overview.data.dispute_type_count.toLocaleString()} />
            <Metric label="決定日期" value={dateRange} />
          </div>
        )}
      </AsyncBlock>

      <section className="panel">
        <PanelHeader title="主要查找方式" />
        <div className="workflow-grid">
          {searchWorkflows.map((workflow) => (
            <article className="workflow-card" key={workflow.key}>
              <div className="workflow-icon">{workflow.icon}</div>
              <div>
                <h3>{workflow.title}</h3>
                <p>{workflow.description}</p>
              </div>
              <button className="secondary-button" type="button" onClick={() => openWorkflow(workflow.key)}>
                {workflow.action}
              </button>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <PanelHeader title="目前資料整理狀態" />
        <div className="data-state-list">
          <div>
            <ShieldCheck size={18} />
            <span>案件資料已統一依年度、爭議類型與案號整理，支援 ROC 114 與 ROC 115 查找。</span>
          </div>
          <div>
            <ShieldCheck size={18} />
            <span>每案保留 decision.pdf、raw_text.txt、normalized_text.txt、metadata.json。</span>
          </div>
          <div>
            <ShieldCheck size={18} />
            <span>語意搜尋目前使用本機 local_hashing_cjk_v1，後續可替換為正式 AI embedding model。</span>
          </div>
        </div>
      </section>
    </section>
  );
}
