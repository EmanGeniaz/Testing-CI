"use client";

export type Tab = "upload" | "schema" | "workbench" | "export";

export interface AppState {
  activeTab: Tab;
  sessionId: string | null;
  filename: string;
  columns: string[];
  rowCount: number;
  preview: Record<string, unknown>[];

  // Dataset context
  datasetType: string;
  focusBrand: string;
  additionalContext: string;

  // Schema
  primaryTextColumn: string;
  visibleColumns: string[];
  aiColumns: string[];

  // LLM config
  provider: string;
  apiKey: string;
  model: string;

  // Analysis
  status: string;
  progress: number;
  analyzedData: Record<string, unknown>[];

  setActiveTab: (tab: Tab) => void;
  setUploadResult: (r: { session_id: string; filename: string; columns: string[]; row_count: number; preview: Record<string, unknown>[] }) => void;
  setContext: (ctx: { datasetType: string; focusBrand: string; additionalContext: string }) => void;
  setSchema: (s: { primaryTextColumn: string; visibleColumns: string[]; aiColumns: string[] }) => void;
  setLLMConfig: (c: { provider: string; apiKey: string; model: string }) => void;
  setProgress: (status: string, progress: number) => void;
  setAnalyzedData: (data: Record<string, unknown>[]) => void;
}

// zustand may not be installed yet; provide a simple fallback using React state
// We'll use a simple module-level store pattern instead

let _state: Omit<AppState, keyof { [K in keyof AppState]: AppState[K] extends Function ? K : never }> = {
  activeTab: "upload",
  sessionId: null,
  filename: "",
  columns: [],
  rowCount: 0,
  preview: [],
  datasetType: "Single brand",
  focusBrand: "",
  additionalContext: "",
  primaryTextColumn: "",
  visibleColumns: [],
  aiColumns: [],
  provider: "groq",
  apiKey: "",
  model: "",
  status: "idle",
  progress: 0,
  analyzedData: [],
};

type Listener = () => void;
const listeners = new Set<Listener>();

function notify() { listeners.forEach(l => l()); }

export const store = {
  get: () => _state as AppState,
  set: (patch: Partial<AppState>) => {
    _state = { ..._state, ...patch };
    notify();
  },
  subscribe: (l: Listener) => {
    listeners.add(l);
    return () => listeners.delete(l);
  },
};
