import React from "react";
import { Activity, BarChart3, BrainCircuit, FileSearch, LayoutDashboard, ListChecks, ListFilter } from "lucide-react";

import { apiGet } from "./api/client";
import { useAsyncData } from "./hooks/useAsyncData";
import { CasesPage } from "./pages/CasesPage";
import { Dashboard } from "./pages/Dashboard";
import { QualityPage } from "./pages/QualityPage";
import { SearchPage } from "./pages/SearchPage";
import { SemanticSearchPage } from "./pages/SemanticSearchPage";
import { StatisticsPage } from "./pages/StatisticsPage";
import type { HealthResponse, Route } from "./types";

const ROUTES: Route[] = ["dashboard", "cases", "search", "semantic", "statistics", "quality"];

function parseRoute(value: string | null): Route | null {
  return ROUTES.includes(value as Route) ? (value as Route) : null;
}

function readUrlState(): { route: Route; selectedCaseId: string | null } {
  const params = new URLSearchParams(window.location.search);
  const caseId = params.get("case_id");
  return {
    route: parseRoute(params.get("view")) ?? (caseId ? "cases" : "dashboard"),
    selectedCaseId: caseId,
  };
}

function writeUrlState(route: Route, selectedCaseId: string | null) {
  const params = new URLSearchParams();
  if (route !== "dashboard") {
    params.set("view", route);
  }
  if (route === "cases" && selectedCaseId) {
    params.set("case_id", selectedCaseId);
  }

  const query = params.toString();
  const nextUrl = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`;
  const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (nextUrl !== currentUrl) {
    window.history.pushState({}, "", nextUrl);
  }
}

export function App() {
  const initialUrlState = React.useMemo(readUrlState, []);
  const [route, setRoute] = React.useState<Route>(initialUrlState.route);
  const [selectedCaseId, setSelectedCaseId] = React.useState<string | null>(initialUrlState.selectedCaseId);
  const health = useAsyncData(() => apiGet<HealthResponse>("/health"), []);

  React.useEffect(() => {
    const handlePopState = () => {
      const nextState = readUrlState();
      setRoute(nextState.route);
      setSelectedCaseId(nextState.selectedCaseId);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigate = React.useCallback((nextRoute: Route, nextCaseId?: string | null) => {
    const resolvedCaseId = nextRoute === "cases" ? nextCaseId ?? selectedCaseId : null;
    setRoute(nextRoute);
    setSelectedCaseId(resolvedCaseId);
    writeUrlState(nextRoute, resolvedCaseId);
  }, [selectedCaseId]);

  const selectCase = React.useCallback((caseId: string) => {
    setRoute("cases");
    setSelectedCaseId(caseId);
    writeUrlState("cases", caseId);
  }, []);

  const navItems: Array<{ route: Route; label: string; icon: React.ReactNode }> = [
    { route: "dashboard", label: "總覽", icon: <LayoutDashboard size={18} /> },
    { route: "cases", label: "案件", icon: <ListFilter size={18} /> },
    { route: "search", label: "搜尋", icon: <FileSearch size={18} /> },
    { route: "semantic", label: "語意搜尋", icon: <BrainCircuit size={18} /> },
    { route: "statistics", label: "統計", icon: <BarChart3 size={18} /> },
    { route: "quality", label: "分析驗證", icon: <ListChecks size={18} /> }
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
              onClick={() => navigate(item.route)}
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
        {route === "dashboard" && <Dashboard onOpenCases={() => navigate("cases")} />}
        {route === "cases" && (
          <CasesPage
            selectedCaseId={selectedCaseId}
            onSelectCase={selectCase}
          />
        )}
        {route === "search" && (
          <SearchPage
            onOpenCase={selectCase}
          />
        )}
        {route === "semantic" && (
          <SemanticSearchPage
            onOpenCase={selectCase}
          />
        )}
        {route === "statistics" && <StatisticsPage />}
        {route === "quality" && <QualityPage />}
      </main>
    </div>
  );
}
