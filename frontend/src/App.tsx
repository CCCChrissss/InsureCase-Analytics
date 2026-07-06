import React from "react";
import { Activity, BarChart3, FileSearch, LayoutDashboard, ListFilter } from "lucide-react";

import { apiGet } from "./api/client";
import { useAsyncData } from "./hooks/useAsyncData";
import { CasesPage } from "./pages/CasesPage";
import { Dashboard } from "./pages/Dashboard";
import { SearchPage } from "./pages/SearchPage";
import { StatisticsPage } from "./pages/StatisticsPage";
import type { HealthResponse, Route } from "./types";

export function App() {
  const [route, setRoute] = React.useState<Route>("dashboard");
  const [selectedCaseId, setSelectedCaseId] = React.useState<string | null>(null);
  const health = useAsyncData(() => apiGet<HealthResponse>("/health"), []);

  const navItems: Array<{ route: Route; label: string; icon: React.ReactNode }> = [
    { route: "dashboard", label: "總覽", icon: <LayoutDashboard size={18} /> },
    { route: "cases", label: "案件", icon: <ListFilter size={18} /> },
    { route: "search", label: "搜尋", icon: <FileSearch size={18} /> },
    { route: "statistics", label: "統計", icon: <BarChart3 size={18} /> }
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Activity size={24} />
          <div>
            <h1>保險評議分析系統</h1>
            <p>FOI ODS 人壽保險案件</p>
          </div>
        </div>
        <nav className="nav-list" aria-label="主要導覽">
          {navItems.map((item) => (
            <button
              key={item.route}
              className={route === item.route ? "nav-button active" : "nav-button"}
              type="button"
              onClick={() => setRoute(item.route)}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-status">
          <span className={health.data?.database_ready ? "status-dot ok" : "status-dot"} />
          <span>{health.loading ? "API 檢查中" : health.data?.database_ready ? "資料庫已連線" : "資料庫未就緒"}</span>
        </div>
      </aside>

      <main className="main-content">
        {route === "dashboard" && <Dashboard onOpenCases={() => setRoute("cases")} />}
        {route === "cases" && (
          <CasesPage
            selectedCaseId={selectedCaseId}
            onSelectCase={(caseId) => setSelectedCaseId(caseId)}
          />
        )}
        {route === "search" && (
          <SearchPage
            onOpenCase={(caseId) => {
              setSelectedCaseId(caseId);
              setRoute("cases");
            }}
          />
        )}
        {route === "statistics" && <StatisticsPage />}
      </main>
    </div>
  );
}
