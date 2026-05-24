"use client";

interface TopNavProps {
  activeTab: string;
  sessionId: string | null;
  onTabChange: (tab: string) => void;
  onHistoryOpen: () => void;
}

const TABS = [
  { id: "upload", label: "Upload" },
  { id: "schema", label: "Schema" },
  { id: "workbench", label: "Workbench" },
  { id: "export", label: "Export" },
];

export default function TopNav({ activeTab, sessionId, onTabChange, onHistoryOpen }: TopNavProps) {
  const activeIdx = TABS.findIndex(t => t.id === activeTab);

  return (
    <header className="sticky top-0 z-50 h-10 bg-white border-b border-[#E8E6DF] flex items-center px-4 gap-0">
      {/* Logo area */}
      <div className="flex items-center gap-1.5 mr-6">
        <div className="w-5 h-5 rounded bg-[#7C3AED] flex items-center justify-center flex-shrink-0">
          <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 12 12">
            <circle cx="6" cy="6" r="4" />
          </svg>
        </div>
      </div>

      {/* Tab pills */}
      <nav className="flex items-center gap-0.5">
        {TABS.map((tab, idx) => {
          const isActive = tab.id === activeTab;
          const isAccessible = idx === 0 || Boolean(sessionId);
          return (
            <button
              key={tab.id}
              onClick={() => isAccessible && onTabChange(tab.id)}
              disabled={!isAccessible}
              className={`flex items-center gap-1.5 h-7 px-3 rounded text-[11px] font-medium transition-all select-none
                ${isActive
                  ? "bg-[#F0EBFF] text-[#7C3AED]"
                  : isAccessible
                    ? "text-[#6B7280] hover:bg-[#F5F4F0] hover:text-[#374151] cursor-pointer"
                    : "text-[#C4C2BB] cursor-not-allowed"
                }`}
            >
              {/* Active indicator dot */}
              {isActive && <span className="w-1.5 h-1.5 rounded-full bg-[#7C3AED]" />}
              {tab.label}
            </button>
          );
        })}
      </nav>

      {/* Right side */}
      <div className="ml-auto flex items-center gap-2">
        {sessionId && (
          <span className="text-[10px] font-mono text-[#9CA3AF] bg-[#F3F2EE] px-2 py-0.5 rounded border border-[#E8E6DF]">
            {sessionId.slice(0, 8)}
          </span>
        )}
        <button
          onClick={onHistoryOpen}
          title="Run History"
          className="flex items-center gap-1.5 h-7 px-2.5 rounded text-[11px] font-medium text-[#6B7280] hover:bg-[#F5F4F0] hover:text-[#7C3AED] transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          History
        </button>
      </div>
    </header>
  );
}
