"use client";
import { useState } from "react";
import TopNav from "./components/TopNav";
import UploadTab from "./components/UploadTab";
import SchemaTab from "./components/SchemaTab";
import WorkbenchTab from "./components/WorkbenchTab";
import ExportTab from "./components/ExportTab";
import RunHistory from "./components/RunHistory";

type Tab = "upload" | "schema" | "workbench" | "export";

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>("upload");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [filename, setFilename] = useState("");
  const [columns, setColumns] = useState<string[]>([]);
  const [rowCount, setRowCount] = useState(0);
  const [historyOpen, setHistoryOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#FDFCF8] flex flex-col">
      <TopNav
        activeTab={activeTab}
        sessionId={sessionId}
        onTabChange={(tab) => setActiveTab(tab as Tab)}
        onHistoryOpen={() => setHistoryOpen(true)}
      />
      {historyOpen && <RunHistory onClose={() => setHistoryOpen(false)} />}

      <main className="flex-1 overflow-auto">
        {activeTab === "upload" && (
          <UploadTab
            onComplete={(data) => {
              setSessionId(data.sessionId);
              setFilename(data.filename);
              setColumns(data.columns);
              setRowCount(data.rowCount);
              setActiveTab("schema");
            }}
          />
        )}

        {activeTab === "schema" && sessionId && (
          <SchemaTab
            sessionId={sessionId}
            columns={columns}
            rowCount={rowCount}
            onComplete={() => setActiveTab("workbench")}
          />
        )}

        {activeTab === "workbench" && sessionId && (
          <div className="h-[calc(100vh-48px)] flex flex-col">
            <WorkbenchTab
              sessionId={sessionId}
              rowCount={rowCount}
              onGoExport={() => setActiveTab("export")}
            />
          </div>
        )}

        {activeTab === "export" && sessionId && (
          <ExportTab sessionId={sessionId} rowCount={rowCount} filename={filename} />
        )}

        {(activeTab === "schema" || activeTab === "workbench" || activeTab === "export") && !sessionId && (
          <div className="flex flex-col items-center justify-center py-32 text-center">
            <p className="text-sm text-[#9CA3AF]">Please upload a dataset first.</p>
            <button onClick={() => setActiveTab("upload")} className="mt-3 text-xs text-[#7C3AED] hover:underline">
              ← Go to Upload
            </button>
          </div>
        )}
      </main>

      {activeTab === "workbench" && sessionId && (
        <div className="fixed bottom-6 right-6 z-50">
          <button
            onClick={() => setActiveTab("export")}
            className="flex items-center gap-2 px-4 py-2.5 bg-[#7C3AED] hover:bg-[#6D28D9] text-white text-sm font-medium rounded-lg shadow-lg transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export
          </button>
        </div>
      )}
    </div>
  );
}
