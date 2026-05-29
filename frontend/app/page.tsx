"use client";
import { useCallback, useState } from "react";
import Sidebar from "./components/Sidebar";
import StudioView from "./components/StudioView";
import AgentWorkspace, { type AgentOption } from "./components/AgentWorkspace";
import AgentTabBar, { type TabDescriptor, type TabStatus } from "./components/AgentTabBar";
import WorkbenchTab from "./components/WorkbenchTab";
import ExportTab from "./components/ExportTab";
import RunHistory from "./components/RunHistory";
import CompareView from "./components/CompareView";

type View = "agents" | "workbench" | "export" | "history" | "compare";

interface TabSession {
  id: string;
  /** null = the picker tab */
  agent: AgentOption | null;
  filename?: string;
  rowCount?: number;
  status: TabStatus;
}

const PICKER_TAB_ID = "picker";

function makeTabId(): string {
  // Browser crypto.randomUUID() exists in modern Chrome/Firefox/Safari.
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `tab-${Math.random().toString(36).slice(2)}-${Date.now().toString(36)}`;
}

export default function Home() {
  const [activeView, setActiveView] = useState<View>("agents");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [filename, setFilename] = useState("");
  const [rowCount, setRowCount] = useState(0);

  const [tabs, setTabs] = useState<TabSession[]>([
    { id: PICKER_TAB_ID, agent: null, status: "idle" },
  ]);
  const [activeTabId, setActiveTabId] = useState<string>(PICKER_TAB_ID);

  const openAgentTab = useCallback((agent: AgentOption) => {
    const newTab: TabSession = {
      id: makeTabId(),
      agent,
      status: "idle",
    };
    setTabs(prev => [...prev, newTab]);
    setActiveTabId(newTab.id);
  }, []);

  const closeTab = useCallback((id: string) => {
    if (id === PICKER_TAB_ID) return; // picker can't be closed
    setTabs(prev => {
      const tab = prev.find(t => t.id === id);
      if (!tab) return prev;
      if (tab.status === "running" || tab.status === "review") {
        if (!window.confirm("This agent is still running. Close the tab and discard progress?")) {
          return prev;
        }
      }
      const next = prev.filter(t => t.id !== id);
      // adjust active tab if needed
      if (id === activeTabId) {
        const idx = prev.findIndex(t => t.id === id);
        const fallback = next[Math.max(0, idx - 1)] ?? next[0];
        setActiveTabId(fallback?.id ?? PICKER_TAB_ID);
      }
      return next;
    });
  }, [activeTabId]);

  const newTab = useCallback(() => {
    // Switch to the picker tab (always present).
    setActiveTabId(PICKER_TAB_ID);
  }, []);

  const updateTabMeta = useCallback(
    (id: string, meta: { filename?: string; rowCount?: number; status: TabStatus }) => {
      setTabs(prev =>
        prev.map(t =>
          t.id === id
            ? {
                ...t,
                filename: meta.filename ?? t.filename,
                rowCount: meta.rowCount ?? t.rowCount,
                status: meta.status,
              }
            : t,
        ),
      );
    },
    [],
  );

  const tabDescriptors: TabDescriptor[] = tabs.map(t => ({
    id: t.id,
    agent: t.agent,
    filename: t.filename,
    rowCount: t.rowCount,
    status: t.status,
  }));

  const showTabBar = activeView === "agents";

  return (
    <div className="flex min-h-screen relative z-[1]">
      <Sidebar
        activeView={activeView}
        onViewChange={setActiveView}
        sessionId={sessionId}
      />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Topbar */}
        <div className="flex items-center px-10 py-3.5 border-b border-rule gap-6 bg-paper/75 backdrop-blur-[20px] sticky top-0 z-20">
          <div className="font-mono text-[11px] text-muted uppercase tracking-[0.12em] flex items-center gap-2">
            <span>Agents</span>
            {activeView !== "agents" && (
              <>
                <span className="text-faint">/</span>
                <span className="text-ink">
                  {activeView === "workbench" ? "Workbench" :
                    activeView === "export" ? "Export" :
                    activeView === "compare" ? "Compare runs" : "Past runs"}
                </span>
              </>
            )}
          </div>
          <div className="ml-auto flex items-center gap-3.5">
            {sessionId && (
              <span className="font-mono text-[10px] text-muted-2 bg-paper-2 px-2.5 py-1 rounded border border-rule">
                {sessionId.slice(0, 8)}
              </span>
            )}
            <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted flex items-center gap-1.5 px-2.5 py-1 bg-green-soft rounded-xl text-green">
              <span className="w-[5px] h-[5px] rounded-full bg-green" />
              Agent ready
            </div>
          </div>
        </div>

        {/* Tab bar — only when on the agents view */}
        {showTabBar && (
          <AgentTabBar
            tabs={tabDescriptors}
            activeTabId={activeTabId}
            onSelect={setActiveTabId}
            onClose={closeTab}
            onNew={newTab}
          />
        )}

        {/* Main content */}
        <main className="flex-1 overflow-auto">
          {activeView === "agents" && (
            <>
              {/* Render ALL tabs at once and toggle visibility with display:none.
                  This is what keeps each tab's state and any in-flight orchestrator
                  stream alive when the user switches tabs. */}
              {tabs.map(tab => (
                <div
                  key={tab.id}
                  style={{ display: tab.id === activeTabId ? "block" : "none" }}
                >
                  {tab.agent === null ? (
                    <StudioView onAgentSelect={openAgentTab} />
                  ) : (
                    <AgentWorkspace
                      agent={tab.agent}
                      onSessionReady={(sid, fname, _cols, rows) => {
                        setSessionId(sid);
                        setFilename(fname);
                        setRowCount(rows);
                      }}
                      onViewReport={() => setActiveView("workbench")}
                      onMetaChange={meta => updateTabMeta(tab.id, meta)}
                    />
                  )}
                </div>
              ))}
            </>
          )}

          {activeView === "workbench" && sessionId && (
            <div className="h-[calc(100vh-53px)] flex flex-col">
              <WorkbenchTab
                sessionId={sessionId}
                rowCount={rowCount}
                onGoExport={() => setActiveView("export")}
              />
            </div>
          )}

          {activeView === "export" && sessionId && (
            <ExportTab sessionId={sessionId} rowCount={rowCount} filename={filename} />
          )}

          {activeView === "history" && (
            <RunHistory onClose={() => setActiveView("agents")} />
          )}

          {activeView === "compare" && (
            <CompareView onGoToAgents={() => setActiveView("agents")} />
          )}

          {(activeView === "workbench" || activeView === "export") && !sessionId && (
            <div className="flex flex-col items-center justify-center py-32 text-center">
              <p className="text-[15px] text-muted" style={{ fontFamily: "var(--font-display)" }}>
                Run an analysis first to see results here.
              </p>
              <button onClick={() => setActiveView("agents")}
                className="mt-4 font-mono text-[11px] text-purple hover:underline uppercase tracking-[0.1em]">
                Go to Agents
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
