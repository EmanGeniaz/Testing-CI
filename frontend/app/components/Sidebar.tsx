"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
  listSkills, uploadSkill, getMethodologySteps,
  getMemoryInsights, resetMemory,
  listMCPConnectors, enableMCPConnector, disableMCPConnector, testMCPConnector,
  type SkillInfo, type MCPConnector, type MemoryInsights,
} from "../lib/api";

type View = "agents" | "workbench" | "export" | "history" | "compare";

interface SidebarProps {
  activeView: View;
  onViewChange: (view: View) => void;
  sessionId: string | null;
}

const WORKSPACE_ITEMS = [
  { id: "agents" as View, label: "Agents", icon: "doc" },
  { id: "workbench" as View, label: "Workbench", icon: "grid" },
  { id: "compare" as View, label: "Compare runs", icon: "compare" },
  { id: "export" as View, label: "Export", icon: "download" },
  { id: "history" as View, label: "Past runs", icon: "clock" },
];

function NavIcon({ type }: { type: string }) {
  const props = { className: "w-[14px] h-[14px] opacity-60 flex-shrink-0", viewBox: "0 0 16 16", fill: "none", stroke: "currentColor", strokeWidth: "1.4" };
  switch (type) {
    case "doc": return <svg {...props}><path d="M2 14V2h7l5 5v7z M9 2v5h5"/></svg>;
    case "grid": return <svg {...props}><path d="M3 3h4v4H3z M9 3h4v4H9z M3 9h4v4H3z M9 9h4v4H9z"/></svg>;
    case "download": return <svg {...props}><path d="M3 10v3h10v-3 M8 2v8 M5 7l3 3 3-3"/></svg>;
    case "clock": return <svg {...props}><circle cx="8" cy="8" r="6"/><path d="M8 4v4l3 2"/></svg>;
    case "compare": return <svg {...props}><rect x="2" y="3" width="7" height="9" rx="1"/><rect x="7" y="6" width="7" height="9" rx="1"/></svg>;
    default: return null;
  }
}

/* ── Collapsible section wrapper ─────────────────────────────────────── */
function SectionHeader({
  label,
  expanded,
  onToggle,
  right,
}: {
  label: string;
  expanded: boolean;
  onToggle: () => void;
  right?: React.ReactNode;
}) {
  return (
    <button
      onClick={onToggle}
      className="w-full font-mono text-[10px] uppercase tracking-[0.16em] text-muted-2 px-[22px] pb-2 font-medium flex items-center gap-1.5 cursor-pointer hover:text-muted transition-colors select-none"
    >
      <span className="text-[8px] text-muted-2 leading-none transition-transform duration-200" style={{ transform: expanded ? "rotate(0deg)" : "rotate(-90deg)" }}>
        &#x25BE;
      </span>
      <span>{label}</span>
      {right && <span className="ml-auto flex items-center" onClick={e => e.stopPropagation()}>{right}</span>}
    </button>
  );
}

function CollapsibleBody({ expanded, children }: { expanded: boolean; children: React.ReactNode }) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState<number | "auto">(expanded ? "auto" : 0);

  useEffect(() => {
    if (!bodyRef.current) return;
    if (expanded) {
      setHeight(bodyRef.current.scrollHeight);
      const t = setTimeout(() => setHeight("auto"), 220);
      return () => clearTimeout(t);
    } else {
      // set explicit height first so transition works from a real value
      setHeight(bodyRef.current.scrollHeight);
      // force reflow then collapse
      requestAnimationFrame(() => {
        requestAnimationFrame(() => setHeight(0));
      });
    }
  }, [expanded]);

  return (
    <div
      style={{
        height: typeof height === "number" ? `${height}px` : "auto",
        overflow: "hidden",
        transition: "height 0.22s ease",
      }}
    >
      <div ref={bodyRef}>{children}</div>
    </div>
  );
}

/* ── Overlay modal shell ─────────────────────────────────────────────── */
function OverlayModal({
  open,
  onClose,
  maxWidth = 640,
  children,
}: {
  open: boolean;
  onClose: () => void;
  maxWidth?: number;
  children: React.ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/35 backdrop-blur-[6px]"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-[14px] border border-rule shadow-[0_16px_48px_rgba(20,19,42,0.18)] w-full mx-4 overflow-hidden flex flex-col"
        style={{ maxWidth, maxHeight: "80vh", animation: "fadeUp 0.25s ease-out both" }}
        onClick={e => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

function ModalHeader({ title, subtitle, icon, onClose }: { title: string; subtitle?: string; icon?: React.ReactNode; onClose: () => void }) {
  return (
    <div className="relative px-6 pt-6 pb-4 border-b border-rule flex items-center justify-between flex-shrink-0">
      {/* Gradient accent bar */}
      <div className="absolute top-0 left-0 right-0 h-[3px] bg-gradient-to-r from-purple to-pink rounded-t-[14px]" />
      <div className="flex items-center gap-3">
        {icon}
        <div>
          <h3 className="text-[18px] font-medium text-ink tracking-[-0.01em]" style={{ fontFamily: "var(--font-display)" }}>
            {title}
          </h3>
          {subtitle && (
            <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted-2 mt-0.5">{subtitle}</div>
          )}
        </div>
      </div>
      <button
        onClick={onClose}
        className="w-8 h-8 rounded-full flex items-center justify-center text-muted hover:text-ink hover:bg-paper-2 transition-colors"
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 2l8 8M10 2l-8 8" /></svg>
      </button>
    </div>
  );
}

/* ── Memory panel body ───────────────────────────────────────────────── */
function PreferenceBar({ label, count, max }: { label: string; count: number; max: number }) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0;
  return (
    <div className="mb-2 last:mb-0">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[12.5px] text-ink-2 truncate pr-2">{label}</span>
        <span className="font-mono text-[10px] text-muted-2 flex-shrink-0">
          {count} {count === 1 ? "run" : "runs"}
        </span>
      </div>
      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--color-rule)" }}>
        <div
          className="h-full rounded-full"
          style={{
            width: `${pct}%`,
            background: "linear-gradient(90deg, var(--color-purple), var(--color-pink))",
          }}
        />
      </div>
    </div>
  );
}

function MemorySectionCard({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="border border-rule rounded-[10px] p-4 mb-3 last:mb-0">
      <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-2 mb-3 flex items-center justify-between">
        <span>{title}</span>
        {hint && <span className="text-muted normal-case tracking-normal text-[10px]">{hint}</span>}
      </div>
      {children}
    </div>
  );
}

function MemoryPanelBody({ insights }: { insights: MemoryInsights }) {
  const rtEntries = Object.entries(insights.report_type_counts || {}).sort((a, b) => b[1] - a[1]);
  const provEntries = Object.entries(insights.provider_counts || {}).sort((a, b) => b[1] - a[1]);
  const domainEntries = Object.entries(insights.dataset_domain_counts || {}).sort((a, b) => b[1] - a[1]);
  const themeEntries = Object.entries(insights.design_theme_counts || {}).sort((a, b) => b[1] - a[1]);

  const maxPref = Math.max(
    1,
    ...rtEntries.map(([, c]) => c),
    ...provEntries.map(([, c]) => c),
    ...themeEntries.map(([, c]) => c),
  );

  const avgMin = insights.avg_duration_seconds != null
    ? (insights.avg_duration_seconds / 60).toFixed(1)
    : null;

  return (
    <div>
      {/* Preferred Patterns */}
      {(rtEntries.length > 0 || provEntries.length > 0 || themeEntries.length > 0) && (
        <MemorySectionCard title="Preferred Patterns" hint="Most-used choices">
          {rtEntries.length > 0 && (
            <div className="mb-3">
              <div className="font-mono text-[9px] text-muted-2 uppercase tracking-[0.08em] mb-1.5">Report type</div>
              {rtEntries.slice(0, 5).map(([k, v]) => (
                <PreferenceBar key={k} label={k} count={v} max={maxPref} />
              ))}
            </div>
          )}
          {provEntries.length > 0 && (
            <div className="mb-3 last:mb-0">
              <div className="font-mono text-[9px] text-muted-2 uppercase tracking-[0.08em] mb-1.5">Provider</div>
              {provEntries.slice(0, 5).map(([k, v]) => (
                <PreferenceBar key={k} label={k} count={v} max={maxPref} />
              ))}
            </div>
          )}
          {themeEntries.length > 0 && (
            <div>
              <div className="font-mono text-[9px] text-muted-2 uppercase tracking-[0.08em] mb-1.5">Design theme</div>
              {themeEntries.slice(0, 5).map(([k, v]) => (
                <PreferenceBar key={k} label={k} count={v} max={maxPref} />
              ))}
            </div>
          )}
        </MemorySectionCard>
      )}

      {/* Refinement requests */}
      {insights.refinement_patterns && insights.refinement_patterns.length > 0 && (
        <MemorySectionCard title="Common Refinement Requests" hint="Auto-applied next run">
          <ul className="space-y-1.5">
            {insights.refinement_patterns.map((p, i) => (
              <li key={i} className="text-[13px] text-ink-2 flex items-center gap-2">
                <span className="w-[5px] h-[5px] rounded-full flex-shrink-0" style={{ background: "var(--color-purple)" }} />
                {p}
              </li>
            ))}
          </ul>
        </MemorySectionCard>
      )}

      {/* Dataset patterns */}
      {domainEntries.length > 0 && (
        <MemorySectionCard title="Dataset Patterns" hint="What you typically analyze">
          <div className="flex flex-wrap gap-1.5">
            {domainEntries.map(([k, v]) => (
              <span
                key={k}
                className="font-mono text-[10px] px-2 py-1 rounded"
                style={{ background: "var(--color-purple-soft)", color: "var(--color-purple)" }}
              >
                {k} <span className="opacity-60">·</span> {v}
              </span>
            ))}
          </div>
        </MemorySectionCard>
      )}

      {/* Quality insights */}
      <MemorySectionCard title="Quality Insights">
        <div className="grid grid-cols-3 gap-3">
          <div>
            <div className="text-[20px] font-medium text-ink leading-none" style={{ fontFamily: "var(--font-display)" }}>
              {insights.avg_findings_per_report ?? "—"}
            </div>
            <div className="font-mono text-[9px] uppercase tracking-[0.08em] text-muted-2 mt-1.5">Avg findings/report</div>
          </div>
          <div>
            <div className="text-[20px] font-medium text-ink leading-none" style={{ fontFamily: "var(--font-display)" }}>
              {insights.avg_refinements_per_run ?? 0}
            </div>
            <div className="font-mono text-[9px] uppercase tracking-[0.08em] text-muted-2 mt-1.5">Avg refinements/run</div>
          </div>
          <div>
            <div className="text-[20px] font-medium text-ink leading-none" style={{ fontFamily: "var(--font-display)" }}>
              {avgMin != null ? `${avgMin}m` : "—"}
            </div>
            <div className="font-mono text-[9px] uppercase tracking-[0.08em] text-muted-2 mt-1.5">Avg run length</div>
          </div>
        </div>
      </MemorySectionCard>
    </div>
  );
}

export default function Sidebar({ activeView, onViewChange, sessionId }: SidebarProps) {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [skillsLoading, setSkillsLoading] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Collapsible section state
  const [expanded, setExpanded] = useState<Record<string, boolean>>({
    workspace: true,
    skills: true,
    connectors: false,
    knowledge: true,
  });
  const toggleSection = (key: string) => setExpanded(prev => ({ ...prev, [key]: !prev[key] }));

  // MCP Connectors state
  const [connectors, setConnectors] = useState<MCPConnector[]>([]);
  const [connectorsLoading, setConnectorsLoading] = useState(true);
  const [selectedConnector, setSelectedConnector] = useState<MCPConnector | null>(null);
  const [connectorConfig, setConnectorConfig] = useState<Record<string, string>>({});
  const [connectorTesting, setConnectorTesting] = useState(false);
  const [connectorTestResult, setConnectorTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [connectorSaving, setConnectorSaving] = useState(false);

  // Knowledge section state
  const [methodologyCount, setMethodologyCount] = useState<number>(0);
  const [memoryCount, setMemoryCount] = useState<number>(0);
  const [knowledgeModal, setKnowledgeModal] = useState<"methodology" | "memory" | null>(null);
  const [methodologySteps, setMethodologySteps] = useState<Array<{ id: number; name: string; description: string; agent_action: string }>>([]);
  const [memoryInsights, setMemoryInsights] = useState<MemoryInsights | null>(null);
  const [resetConfirm, setResetConfirm] = useState(false);
  const [resetting, setResetting] = useState(false);

  const fetchSkills = useCallback(async () => {
    try {
      const data = await listSkills();
      setSkills(data.skills);
    } catch {
      // Silently fall back to empty — API may not be up yet
      setSkills([]);
    } finally {
      setSkillsLoading(false);
    }
  }, []);

  const fetchConnectors = useCallback(async () => {
    try {
      const data = await listMCPConnectors();
      setConnectors(data.connectors);
    } catch {
      setConnectors([]);
    } finally {
      setConnectorsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

  useEffect(() => {
    fetchConnectors();
  }, [fetchConnectors]);

  // Fetch methodology step count and memory count
  useEffect(() => {
    getMethodologySteps()
      .then(res => {
        setMethodologyCount(res.steps.length);
        setMethodologySteps(res.steps);
      })
      .catch(() => {});
    getMemoryInsights()
      .then(res => {
        setMemoryCount(res.total_runs);
        setMemoryInsights(res);
      })
      .catch(() => {});
  }, []);

  const refreshMemory = useCallback(() => {
    getMemoryInsights()
      .then(res => {
        setMemoryCount(res.total_runs);
        setMemoryInsights(res);
      })
      .catch(() => {});
  }, []);

  const handleResetMemory = useCallback(async () => {
    setResetting(true);
    try {
      await resetMemory();
      setResetConfirm(false);
      refreshMemory();
    } catch (err) {
      console.error("Failed to reset memory:", err);
    } finally {
      setResetting(false);
    }
  }, [refreshMemory]);

  const handleSkillUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      await uploadSkill({
        name: parsed.name || file.name.replace(".json", ""),
        description: parsed.description || "",
        trigger_words: parsed.trigger_words || [],
      });
      await fetchSkills();
    } catch (err) {
      console.error("Skill upload failed:", err);
    }
    // Reset input so the same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const openConnectorPanel = (connector: MCPConnector) => {
    setSelectedConnector(connector);
    // Pre-fill config from existing user_config (replacing masked values with empty)
    const initial: Record<string, string> = {};
    for (const field of connector.config_fields) {
      const existing = connector.user_config[field.key];
      initial[field.key] = existing === "********" ? "" : (existing || "");
    }
    setConnectorConfig(initial);
    setConnectorTestResult(null);
  };

  const closeConnectorPanel = useCallback(() => setSelectedConnector(null), []);

  const handleConnectorSave = async () => {
    if (!selectedConnector) return;
    setConnectorSaving(true);
    try {
      await enableMCPConnector(selectedConnector.id, connectorConfig);
      await fetchConnectors();
      setSelectedConnector(null);
    } catch (err) {
      console.error("Failed to enable connector:", err);
    } finally {
      setConnectorSaving(false);
    }
  };

  const handleConnectorDisable = async () => {
    if (!selectedConnector) return;
    setConnectorSaving(true);
    try {
      await disableMCPConnector(selectedConnector.id);
      await fetchConnectors();
      setSelectedConnector(null);
    } catch (err) {
      console.error("Failed to disable connector:", err);
    } finally {
      setConnectorSaving(false);
    }
  };

  const handleConnectorTest = async () => {
    if (!selectedConnector) return;
    setConnectorTesting(true);
    setConnectorTestResult(null);
    try {
      const result = await testMCPConnector(selectedConnector.id);
      setConnectorTestResult(result);
    } catch {
      setConnectorTestResult({ success: false, message: "Test request failed" });
    } finally {
      setConnectorTesting(false);
    }
  };

  const closeKnowledgeModal = useCallback(() => setKnowledgeModal(null), []);

  return (
    <aside className="border-r border-rule bg-white/70 backdrop-blur-[20px] py-[22px] flex flex-col sticky top-0 h-screen overflow-y-auto w-[240px] flex-shrink-0">
      {/* Brand */}
      <div className="px-[22px] pb-[22px]">
        <div className="font-[var(--font-display)] font-medium text-[22px] leading-[1.05] tracking-[-0.025em] text-ink"
          style={{ fontFamily: "var(--font-display)" }}>
          InfoVision
        </div>
        <div className="font-italic text-[15px] leading-[1.1] tracking-[-0.015em] mt-[2px] gradient-text-subtle"
          style={{ fontFamily: "var(--font-display)", fontStyle: "italic" }}>
          Consumer Intelligence
        </div>
      </div>

      {/* Search */}
      <div className="mx-[18px] mb-[24px] px-3 py-2 bg-white border border-rule rounded-[6px] flex items-center gap-[9px] text-[12.5px] text-muted cursor-text hover:border-purple-rule hover:shadow-[0_1px_3px_rgba(108,76,255,0.08)] transition-all">
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4"><circle cx="7" cy="7" r="5"/><path d="M11 11l3 3"/></svg>
        <span>Search or ask</span>
        <span className="ml-auto font-mono text-[10px] px-1.5 py-0.5 bg-paper-2 border border-rule rounded text-muted">&#x2318;K</span>
      </div>

      {/* ── Workspace ──────────────────────────────────────────────────── */}
      <div className="mb-[22px]">
        <SectionHeader label="Workspace" expanded={expanded.workspace} onToggle={() => toggleSection("workspace")} />
        <CollapsibleBody expanded={expanded.workspace}>
          {WORKSPACE_ITEMS.map(item => {
            const isActive = activeView === item.id;
            const isDisabled = item.id !== "agents" && item.id !== "history" && item.id !== "compare" && !sessionId;
            return (
              <button
                key={item.id}
                onClick={() => !isDisabled && onViewChange(item.id)}
                disabled={isDisabled}
                className={`w-full text-left py-1.5 px-[22px] text-[13px] flex items-center gap-[11px] relative transition-colors tracking-[-0.005em]
                  ${isActive ? "text-ink font-medium" : isDisabled ? "text-faint cursor-not-allowed" : "text-ink-3 hover:text-ink cursor-pointer"}`}
              >
                {isActive && (
                  <span className="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-r bg-gradient-to-b from-purple to-pink" />
                )}
                <NavIcon type={item.icon} />
                {item.label}
              </button>
            );
          })}
        </CollapsibleBody>
      </div>

      {/* ── Skills ─────────────────────────────────────────────────────── */}
      <div className="mb-[22px]">
        <SectionHeader
          label="Skills"
          expanded={expanded.skills}
          onToggle={() => toggleSection("skills")}
          right={
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-[16px] h-[16px] rounded flex items-center justify-center text-muted hover:text-ink hover:bg-paper-2 transition-colors"
              title="Upload skill (.json)"
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.4">
                <path d="M5 1v8M1 5h8" />
              </svg>
            </button>
          }
        />
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          onChange={handleSkillUpload}
          className="hidden"
        />
        <CollapsibleBody expanded={expanded.skills}>
          <div className="px-[22px] pl-[47px] flex flex-col gap-1">
            {skillsLoading ? (
              <div className="font-mono text-[11px] text-muted">Loading...</div>
            ) : skills.length === 0 ? (
              <div className="font-mono text-[11px] text-muted">No skills loaded</div>
            ) : (
              skills.map(skill => (
                <div key={skill.id} className="font-mono text-[11px] text-muted flex items-center gap-2 cursor-pointer hover:text-ink-2 transition-colors" title={skill.description}>
                  <span className="w-[5px] h-[5px] rounded-full bg-green flex-shrink-0" />
                  {skill.name}
                </div>
              ))
            )}
          </div>
        </CollapsibleBody>
      </div>

      {/* ── Connectors ─────────────────────────────────────────────────── */}
      <div className="mb-[22px]">
        <SectionHeader label="Connectors" expanded={expanded.connectors} onToggle={() => toggleSection("connectors")} />
        <CollapsibleBody expanded={expanded.connectors}>
          <div className="px-[22px] pl-[22px] flex flex-col gap-0.5">
            {connectorsLoading ? (
              <div className="font-mono text-[11px] text-muted pl-[25px]">Loading...</div>
            ) : connectors.length === 0 ? (
              <div className="font-mono text-[11px] text-muted pl-[25px]">No connectors</div>
            ) : (
              connectors.map(connector => {
                const isComingSoon = connector.status === "coming_soon";
                const isAlwaysOn = connector.always_enabled;
                const isEnabled = connector.enabled;
                return (
                  <button
                    key={connector.id}
                    onClick={() => !isComingSoon && openConnectorPanel(connector)}
                    disabled={isComingSoon}
                    className={`w-full text-left py-1 px-0 text-[12px] flex items-center gap-[9px] transition-colors rounded
                      ${isComingSoon ? "text-faint cursor-not-allowed" : "text-ink-3 hover:text-ink cursor-pointer"}`}
                    title={connector.description}
                  >
                    <span className="text-[13px] w-[18px] text-center flex-shrink-0">{connector.icon}</span>
                    <span className="truncate flex-1 font-mono text-[11px]">{connector.name}</span>
                    {isComingSoon ? (
                      <svg className="w-[11px] h-[11px] opacity-40 flex-shrink-0" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6">
                        <rect x="3" y="7" width="10" height="7" rx="1.5"/><path d="M5 7V5a3 3 0 0 1 6 0v2"/>
                      </svg>
                    ) : isAlwaysOn ? (
                      <span className="w-[6px] h-[6px] rounded-full bg-purple flex-shrink-0" title="Always on" />
                    ) : isEnabled ? (
                      <span className="w-[6px] h-[6px] rounded-full bg-green flex-shrink-0" title="Enabled" />
                    ) : (
                      <span className="w-[6px] h-[6px] rounded-full bg-faint flex-shrink-0" title="Disabled" />
                    )}
                  </button>
                );
              })
            )}
          </div>
        </CollapsibleBody>
      </div>

      {/* ── Connector config modal (full-screen overlay) ───────────────── */}
      <OverlayModal open={!!selectedConnector} onClose={closeConnectorPanel} maxWidth={520}>
        {selectedConnector && (
          <>
            <ModalHeader
              title={selectedConnector.name}
              subtitle={selectedConnector.category.replace(/_/g, " ")}
              icon={<span className="text-[24px]">{selectedConnector.icon}</span>}
              onClose={closeConnectorPanel}
            />
            <div className="p-6 overflow-y-auto">
              <p className="text-[13px] text-muted leading-[1.5] mb-5">{selectedConnector.description}</p>

              {selectedConnector.always_enabled ? (
                <div className="flex items-center gap-2 py-3 px-4 bg-purple-soft rounded-[8px]">
                  <span className="w-[6px] h-[6px] rounded-full bg-purple flex-shrink-0" />
                  <span className="font-mono text-[11px] text-purple font-medium">Always enabled</span>
                </div>
              ) : (
                <>
                  {/* Config fields */}
                  {selectedConnector.config_fields.length > 0 && (
                    <div className="space-y-3 mb-5">
                      {selectedConnector.config_fields.map(field => (
                        <div key={field.key}>
                          <label className="block font-mono text-[10px] uppercase tracking-[0.1em] text-muted-2 mb-1.5">
                            {field.label}{field.required && <span className="text-pink ml-0.5">*</span>}
                          </label>
                          <input
                            type={field.type === "password" ? "password" : "text"}
                            value={connectorConfig[field.key] || ""}
                            onChange={e => setConnectorConfig(prev => ({ ...prev, [field.key]: e.target.value }))}
                            placeholder={field.placeholder || `Enter ${field.label.toLowerCase()}`}
                            className="w-full px-3 py-2 bg-white border border-rule rounded-[6px] text-[13px] text-ink placeholder:text-faint focus:outline-none focus:border-purple-rule focus:shadow-[0_1px_3px_rgba(108,76,255,0.08)] transition-all"
                          />
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Test result */}
                  {connectorTestResult && (
                    <div className={`mb-4 py-2.5 px-4 rounded-[8px] font-mono text-[11px] ${
                      connectorTestResult.success
                        ? "bg-green-soft text-green"
                        : "bg-pink-soft text-pink"
                    }`}>
                      {connectorTestResult.message}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleConnectorSave}
                      disabled={connectorSaving}
                      className="flex-1 py-2.5 rounded-[8px] font-mono text-[11px] font-medium uppercase tracking-[0.1em] text-white bg-gradient-to-r from-purple to-pink hover:shadow-[0_4px_16px_rgba(108,76,255,0.25)] transition-all disabled:opacity-50"
                    >
                      {connectorSaving ? "Saving..." : selectedConnector.enabled ? "Update" : "Enable"}
                    </button>
                    {selectedConnector.enabled && (
                      <>
                        <button
                          onClick={handleConnectorTest}
                          disabled={connectorTesting}
                          className="py-2.5 px-4 rounded-[8px] font-mono text-[11px] font-medium uppercase tracking-[0.1em] text-purple border border-purple-rule hover:bg-purple-soft transition-all disabled:opacity-50"
                        >
                          {connectorTesting ? "Testing..." : "Test"}
                        </button>
                        <button
                          onClick={handleConnectorDisable}
                          disabled={connectorSaving}
                          className="py-2.5 px-4 rounded-[8px] font-mono text-[11px] font-medium uppercase tracking-[0.1em] text-muted border border-rule hover:text-pink hover:border-pink-soft transition-all disabled:opacity-50"
                        >
                          Disable
                        </button>
                      </>
                    )}
                  </div>
                </>
              )}
            </div>
          </>
        )}
      </OverlayModal>

      {/* ── Knowledge ──────────────────────────────────────────────────── */}
      <div className="mb-[22px]">
        <SectionHeader label="Knowledge" expanded={expanded.knowledge} onToggle={() => toggleSection("knowledge")} />
        <CollapsibleBody expanded={expanded.knowledge}>
          <button
            onClick={() => setKnowledgeModal("methodology")}
            className="w-full py-1.5 px-[22px] text-[13px] text-ink-3 flex items-center gap-[11px] cursor-pointer hover:text-ink transition-colors text-left"
          >
            <svg className="w-[14px] h-[14px] opacity-60" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
              <path d="M2 4h12 M2 8h12 M2 12h12"/>
            </svg>
            Methodology
            {methodologyCount > 0 && (
              <span className="ml-auto font-mono text-[9px] px-1.5 py-0.5 bg-purple-soft text-purple rounded font-medium">
                {methodologyCount} steps
              </span>
            )}
          </button>
          <button
            onClick={() => setKnowledgeModal("memory")}
            className="w-full py-1.5 px-[22px] text-[13px] text-ink-3 flex items-center gap-[11px] cursor-pointer hover:text-ink transition-colors text-left"
          >
            <svg className="w-[14px] h-[14px] opacity-60" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
              <path d="M2 4h12 M2 8h12 M2 12h12"/>
            </svg>
            Memory
            <span className="ml-auto font-mono text-[9px] px-1.5 py-0.5 bg-paper-2 text-muted rounded font-medium">
              {memoryCount > 0 ? `${memoryCount} learned` : "0 learned"}
            </span>
          </button>
        </CollapsibleBody>
      </div>

      {/* ── Methodology modal (full-screen overlay) ────────────────────── */}
      <OverlayModal open={knowledgeModal === "methodology"} onClose={closeKnowledgeModal} maxWidth={640}>
        <ModalHeader title="Research Methodology" onClose={closeKnowledgeModal} />
        <div className="p-6 overflow-y-auto">
          {methodologySteps.length === 0 ? (
            <p className="text-[13px] text-muted text-center py-6">No methodology steps configured yet.</p>
          ) : (
            <ol className="space-y-4">
              {methodologySteps.map((step, idx) => (
                <li key={step.id} className="flex gap-4">
                  <div className="w-7 h-7 rounded-full bg-gradient-to-r from-purple to-pink text-white text-[11px] font-mono font-bold flex items-center justify-center shrink-0 mt-0.5">
                    {idx + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[14px] font-medium text-ink leading-snug" style={{ fontFamily: "var(--font-display)" }}>
                      {step.name}
                    </div>
                    <p className="text-[12.5px] text-muted leading-[1.55] mt-1">
                      {step.description}
                    </p>
                    <div className="font-mono text-[9px] text-purple uppercase tracking-[0.08em] mt-1.5 py-1 px-2 bg-purple-soft rounded inline-block">
                      {step.agent_action}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </OverlayModal>

      {/* ── Memory modal (full-screen overlay) ─────────────────────────── */}
      <OverlayModal open={knowledgeModal === "memory"} onClose={closeKnowledgeModal} maxWidth={720}>
        <ModalHeader
          title="What the agents have learned"
          subtitle={`${memoryCount} runs analyzed`}
          onClose={closeKnowledgeModal}
        />
        <div className="p-6 overflow-y-auto">
          <p className="text-[13px] text-muted leading-[1.55] mb-5">
            Memory is built from your past runs. The orchestrator reads this back at the start
            of every new run and applies your common refinement patterns up front.
          </p>

          {memoryInsights && memoryCount > 0 ? (
            <MemoryPanelBody insights={memoryInsights} />
          ) : (
            <p className="text-[13px] text-muted leading-[1.5] text-center max-w-[420px] mx-auto py-6">
              No runs analyzed yet. As you run analyses, the agent will learn your preferences
              for report types, design themes, and refinement patterns.
            </p>
          )}

          {/* Reset memory section */}
          <div className="border-t border-rule mt-6 pt-5">
            {!resetConfirm ? (
              <button
                onClick={() => setResetConfirm(true)}
                disabled={memoryCount === 0}
                className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted hover:text-pink transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Reset memory
              </button>
            ) : (
              <div className="bg-pink-soft border border-pink-soft rounded-[8px] p-4 flex items-center gap-3 flex-wrap">
                <div className="flex-1 min-w-[200px]">
                  <div className="text-[13px] font-medium text-ink mb-0.5">Reset all learned memory?</div>
                  <div className="font-mono text-[10px] text-muted">
                    This clears {memoryCount} runs of preferences and refinement patterns. Cannot be undone.
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setResetConfirm(false)}
                    disabled={resetting}
                    className="py-1.5 px-3 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.1em] text-muted border border-rule hover:text-ink transition-colors disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleResetMemory}
                    disabled={resetting}
                    className="py-1.5 px-3 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.1em] font-medium text-white bg-pink hover:opacity-90 transition-opacity disabled:opacity-50"
                  >
                    {resetting ? "Resetting..." : "Yes, reset"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </OverlayModal>

      {/* Footer */}
      <div className="mt-auto pt-[18px] px-[22px] border-t border-rule flex items-center gap-[11px]">
        <div className="w-[30px] h-[30px] rounded-full bg-gradient-to-br from-purple to-pink text-white font-mono text-[11px] font-medium flex items-center justify-center">
          ED
        </div>
        <div>
          <div className="text-[13px] text-ink font-medium">Emanuel Davidson</div>
          <div className="font-mono text-[10px] text-muted-2 uppercase tracking-[0.1em]">Research Lead</div>
        </div>
      </div>
    </aside>
  );
}
