"use client";
import { useState } from "react";
import Sidebar from "./components/Sidebar";
import StudioView from "./components/StudioView";
import WorkbenchTab from "./components/WorkbenchTab";
import ExportTab from "./components/ExportTab";
import RunHistory from "./components/RunHistory";

type View = "studio" | "workbench" | "export" | "history";

export default function Home() {
  const [activeView, setActiveView] = useState<View>("studio");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [filename, setFilename] = useState("");
  const [columns, setColumns] = useState<string[]>([]);
  const [rowCount, setRowCount] = useState(0);

  return (
    <div className="flex min-h-screen relative z-[1]">
      <Sidebar
        activeView={activeView}
        onViewChange={setActiveView}
        sessionId={sessionId}
      />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Topbar */}
        <div className="flex items-center px-10 py-3.5 border-b border-rule gap-6 bg-paper/75 backdrop-blur-[20px] sticky top-0 z-10">
          <div className="font-mono text-[11px] text-muted uppercase tracking-[0.12em] flex items-center gap-2">
            <span>Studio</span>
            <span className="text-faint">/</span>
            <span className="text-ink">
              {activeView === "studio" ? "New report" :
                activeView === "workbench" ? "Workbench" :
                activeView === "export" ? "Export" : "Past runs"}
            </span>
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

        {/* Main content */}
        <main className="flex-1 overflow-auto">
          {activeView === "studio" && (
            <StudioView
              sessionId={sessionId}
              onSessionReady={(sid, fname, cols, rows) => {
                setSessionId(sid);
                setFilename(fname);
                setColumns(cols);
                setRowCount(rows);
              }}
              onViewReport={() => setActiveView("workbench")}
            />
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
            <RunHistory onClose={() => setActiveView("studio")} />
          )}

          {(activeView === "workbench" || activeView === "export") && !sessionId && (
            <div className="flex flex-col items-center justify-center py-32 text-center">
              <p className="text-[15px] text-muted" style={{ fontFamily: "var(--font-display)" }}>
                Run an analysis first to see results here.
              </p>
              <button onClick={() => setActiveView("studio")}
                className="mt-4 font-mono text-[11px] text-purple hover:underline uppercase tracking-[0.1em]">
                Go to Studio
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
