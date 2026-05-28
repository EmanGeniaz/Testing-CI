"use client";

import type { AgentOption } from "./AgentInspectorModal";

export type TabStatus = "idle" | "running" | "review" | "complete" | "error";

export interface TabDescriptor {
  id: string;
  /** null = picker tab */
  agent: AgentOption | null;
  filename?: string;
  rowCount?: number;
  status: TabStatus;
}

interface AgentTabBarProps {
  tabs: TabDescriptor[];
  activeTabId: string;
  onSelect: (id: string) => void;
  onClose: (id: string) => void;
  onNew: () => void;
}

export default function AgentTabBar({
  tabs,
  activeTabId,
  onSelect,
  onClose,
  onNew,
}: AgentTabBarProps) {
  return (
    <div
      className="flex items-end gap-1 px-4 pt-2 sticky top-0 z-50 min-h-[44px] border-b border-rule"
      style={{
        background: "rgba(255,255,255,0.85)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
      }}
    >
      {tabs.map(tab => (
        <TabPill
          key={tab.id}
          tab={tab}
          active={tab.id === activeTabId}
          onSelect={() => onSelect(tab.id)}
          onClose={() => onClose(tab.id)}
        />
      ))}
      <button
        type="button"
        onClick={onNew}
        className="flex items-center gap-1.5 px-3 py-2 -mb-[1px] rounded-t-[8px] font-mono text-[11px] uppercase tracking-[0.1em] font-medium text-muted hover:text-purple hover:bg-purple-soft transition-all"
        style={{
          background: "transparent",
          border: "1px dashed var(--color-rule-2)",
          borderBottom: "none",
        }}
      >
        + New agent
      </button>
    </div>
  );
}

function TabPill({
  tab,
  active,
  onSelect,
  onClose,
}: {
  tab: TabDescriptor;
  active: boolean;
  onSelect: () => void;
  onClose: () => void;
}) {
  const isPicker = tab.agent === null;
  const label = isPicker
    ? "Agents"
    : tab.filename
      ? `${tab.agent!.name} · ${tab.filename}`
      : tab.agent!.name;

  return (
    <div
      role="tab"
      aria-selected={active}
      onClick={onSelect}
      onKeyDown={e => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
      tabIndex={0}
      className={`group relative flex items-center gap-2 px-3.5 py-2 -mb-[1px] rounded-t-[8px] text-[12px] cursor-pointer transition-all max-w-[220px] min-w-[140px] ${
        active
          ? "bg-paper text-ink font-medium z-[2]"
          : "text-muted hover:bg-paper hover:text-ink-2"
      }`}
      style={{
        background: active ? "var(--color-paper)" : "var(--color-paper-2)",
        border: "1px solid var(--color-rule)",
        borderBottom: "none",
      }}
    >
      {active && (
        <span
          aria-hidden
          className="absolute top-0 left-0 right-0 h-[2px] rounded-t-[8px] pointer-events-none"
          style={{
            background: "linear-gradient(90deg, var(--color-purple), var(--color-pink))",
          }}
        />
      )}

      {isPicker ? (
        <span
          aria-hidden
          className="w-[18px] h-[18px] rounded-[5px] flex items-center justify-center text-white font-mono text-[10px] font-bold flex-shrink-0"
          style={{
            background:
              "linear-gradient(135deg, var(--color-purple), var(--color-pink))",
          }}
        >
          ＋
        </span>
      ) : (
        <span
          aria-hidden
          className="w-[18px] h-[18px] rounded-[5px] flex items-center justify-center text-white font-mono text-[9px] font-bold flex-shrink-0"
          style={{ background: tab.agent!.gradient }}
        >
          {tab.agent!.initials}
        </span>
      )}

      <span className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap text-[12px]">
        {label}
      </span>

      {!isPicker && <StatusDot status={tab.status} />}

      {!isPicker && (
        <button
          type="button"
          onClick={e => {
            e.stopPropagation();
            onClose();
          }}
          className={`w-[18px] h-[18px] rounded-[4px] flex items-center justify-center text-muted-2 hover:bg-rule hover:text-ink flex-shrink-0 transition-all ${
            active ? "opacity-100" : "opacity-0 group-hover:opacity-100"
          }`}
          aria-label="Close tab"
        >
          <svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M2 2l8 8M10 2l-8 8" />
          </svg>
        </button>
      )}
    </div>
  );
}

function StatusDot({ status }: { status: TabStatus }) {
  if (status === "idle") return null;
  const colorMap: Record<Exclude<TabStatus, "idle">, string> = {
    running: "var(--color-purple)",
    review: "var(--color-amber)",
    complete: "var(--color-green)",
    error: "var(--color-pink)",
  };
  const title: Record<Exclude<TabStatus, "idle">, string> = {
    running: "Running",
    review: "Needs approval",
    complete: "Complete",
    error: "Error",
  };
  const isRunning = status === "running";
  return (
    <span
      title={title[status]}
      aria-label={title[status]}
      className="w-[6px] h-[6px] rounded-full flex-shrink-0"
      style={{
        background: colorMap[status],
        animation: isRunning ? "agentTabPulse 1.5s ease-in-out infinite" : undefined,
      }}
    >
      <style jsx>{`
        @keyframes agentTabPulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.85); }
        }
      `}</style>
    </span>
  );
}
