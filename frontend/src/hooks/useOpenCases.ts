import React from "react";

const STORAGE_KEY = "insurecase.open-case-tabs.v1";

export type OpenCaseTab = {
  caseId: string;
  label: string;
};

type OpenCaseState = {
  tabs: OpenCaseTab[];
  activeCaseId: string | null;
  lastActiveCaseId: string | null;
};

type OpenCaseAction =
  | { type: "open"; caseId: string; label?: string }
  | { type: "select"; caseId: string }
  | { type: "rename"; caseId: string; label: string }
  | { type: "close"; caseId: string }
  | { type: "minimize" }
  | { type: "restore" };

export function useOpenCases() {
  const [state, dispatch] = React.useReducer(openCaseReducer, undefined, readStoredState);
  const openCase = React.useCallback((caseId: string, label?: string) => {
    dispatch({ type: "open", caseId, label });
  }, []);
  const selectCase = React.useCallback((caseId: string) => dispatch({ type: "select", caseId }), []);
  const renameCase = React.useCallback((caseId: string, label: string) => {
    dispatch({ type: "rename", caseId, label });
  }, []);
  const closeCase = React.useCallback((caseId: string) => dispatch({ type: "close", caseId }), []);
  const minimize = React.useCallback(() => dispatch({ type: "minimize" }), []);
  const restore = React.useCallback(() => dispatch({ type: "restore" }), []);

  React.useEffect(() => {
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // Session persistence is optional; the in-memory workspace remains usable.
    }
  }, [state]);

  return {
    ...state,
    openCase,
    selectCase,
    renameCase,
    closeCase,
    minimize,
    restore,
  };
}

function openCaseReducer(state: OpenCaseState, action: OpenCaseAction): OpenCaseState {
  if (action.type === "open") {
    const existing = state.tabs.find((tab) => tab.caseId === action.caseId);
    const label = action.label?.trim() || existing?.label || "案件載入中";
    const tabs = existing
      ? state.tabs.map((tab) => (tab.caseId === action.caseId ? { ...tab, label } : tab))
      : [...state.tabs, { caseId: action.caseId, label }];
    return { tabs, activeCaseId: action.caseId, lastActiveCaseId: action.caseId };
  }

  if (action.type === "select") {
    if (!state.tabs.some((tab) => tab.caseId === action.caseId)) return state;
    return { ...state, activeCaseId: action.caseId, lastActiveCaseId: action.caseId };
  }

  if (action.type === "rename") {
    const label = action.label.trim();
    if (!label) return state;
    const current = state.tabs.find((tab) => tab.caseId === action.caseId);
    if (!current || current.label === label) return state;
    return {
      ...state,
      tabs: state.tabs.map((tab) => (tab.caseId === action.caseId ? { ...tab, label } : tab)),
    };
  }

  if (action.type === "close") {
    const closingIndex = state.tabs.findIndex((tab) => tab.caseId === action.caseId);
    if (closingIndex < 0) return state;
    const tabs = state.tabs.filter((tab) => tab.caseId !== action.caseId);
    if (state.activeCaseId !== action.caseId) {
      return {
        ...state,
        tabs,
        lastActiveCaseId: state.lastActiveCaseId === action.caseId ? tabs[0]?.caseId ?? null : state.lastActiveCaseId,
      };
    }
    const nextActive = tabs[closingIndex]?.caseId ?? tabs[closingIndex - 1]?.caseId ?? null;
    return { tabs, activeCaseId: nextActive, lastActiveCaseId: nextActive };
  }

  if (action.type === "minimize") {
    return { ...state, activeCaseId: null };
  }

  if (action.type === "restore") {
    const activeCaseId = state.tabs.some((tab) => tab.caseId === state.lastActiveCaseId)
      ? state.lastActiveCaseId
      : state.tabs[0]?.caseId ?? null;
    return { ...state, activeCaseId };
  }

  return state;
}

function readStoredState(): OpenCaseState {
  try {
    const stored = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) || "null") as Partial<OpenCaseState> | null;
    const tabs = Array.isArray(stored?.tabs)
      ? stored.tabs.filter(isOpenCaseTab)
      : [];
    const activeCaseId = typeof stored?.activeCaseId === "string"
      && tabs.some((tab) => tab.caseId === stored.activeCaseId)
      ? stored.activeCaseId
      : null;
    const lastActiveCaseId = typeof stored?.lastActiveCaseId === "string"
      && tabs.some((tab) => tab.caseId === stored.lastActiveCaseId)
      ? stored.lastActiveCaseId
      : tabs[0]?.caseId ?? null;
    return { tabs, activeCaseId, lastActiveCaseId };
  } catch {
    return { tabs: [], activeCaseId: null, lastActiveCaseId: null };
  }
}

function isOpenCaseTab(value: unknown): value is OpenCaseTab {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<OpenCaseTab>;
  return typeof candidate.caseId === "string" && typeof candidate.label === "string";
}
