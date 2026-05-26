"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
  listSkills, uploadSkill, getMethodologySteps, getLearnedPreferences,
  listMCPConnectors, enableMCPConnector, disableMCPConnector, testMCPConnector,
  type SkillInfo, type MCPConnector,
} from "../lib/api";

type View = "studio" | "workbench" | "export" | "history";

interface SidebarProps {
  activeView: View;
  onViewChange: (view: View) => void;
  sessionId: string | null;
}

const WORKSPACE_ITEMS = [
  { id: "studio" as View, label: "Studio", icon: "doc" },
  { id: "workbench" as View, label: "Workbench", icon: "grid" },
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
    default: return null;
  }
}

export default function Sidebar({ activeView, onViewChange, sessionId }: SidebarProps) {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [skillsLoading, setSkillsLoading] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    getLearnedPreferences()
      .then(res => { setMemoryCount(res.total_runs); })
      .catch(() => {});
  }, []);

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
    } catch (err) {
      setConnectorTestResult({ success: false, message: "Test request failed" });
    } finally {
      setConnectorTesting(false);
    }
  };

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
        <span className="ml-auto font-mono text-[10px] px-1.5 py-0.5 bg-paper-2 border border-rule rounded text-muted">⌘K</span>
      </div>

      {/* Workspace nav */}
      <div className="mb-[22px]">
        <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-2 px-[22px] pb-2 font-medium">
          Workspace
        </div>
        {WORKSPACE_ITEMS.map(item => {
          const isActive = activeView === item.id;
          const isDisabled = item.id !== "studio" && item.id !== "history" && !sessionId;
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
      </div>

      {/* Skills */}
      <div className="mb-[22px]">
        <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-2 px-[22px] pb-2 font-medium flex items-center justify-between">
          <span>Skills</span>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="w-[16px] h-[16px] rounded flex items-center justify-center text-muted hover:text-ink hover:bg-paper-2 transition-colors"
            title="Upload skill (.json)"
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.4">
              <path d="M5 1v8M1 5h8" />
            </svg>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            onChange={handleSkillUpload}
            className="hidden"
          />
        </div>
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
      </div>

      {/* Connectors */}
      <div className="mb-[22px]">
        <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-2 px-[22px] pb-2 font-medium">
          Connectors
        </div>
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
      </div>

      {/* Connector config modal */}
      {selectedConnector && (
        <div
          className="fixed inset-0 bg-black/30 backdrop-blur-[4px] z-50 flex items-center justify-center"
          onClick={() => setSelectedConnector(null)}
        >
          <div
            className="bg-white rounded-[14px] border border-rule shadow-[0_12px_40px_rgba(20,19,42,0.15)] max-w-[480px] w-full mx-4 max-h-[80vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}
            style={{ animation: "fadeUp 0.25s ease-out both" }}
          >
            {/* Header */}
            <div className="px-6 pt-6 pb-4 border-b border-rule flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-[22px]">{selectedConnector.icon}</span>
                <div>
                  <h3 className="text-[17px] font-medium text-ink tracking-[-0.01em]" style={{ fontFamily: "var(--font-display)" }}>
                    {selectedConnector.name}
                  </h3>
                  <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted-2 mt-0.5">
                    {selectedConnector.category.replace(/_/g, " ")}
                  </div>
                </div>
              </div>
              <button
                onClick={() => setSelectedConnector(null)}
                className="w-7 h-7 rounded-full flex items-center justify-center text-muted hover:text-ink hover:bg-paper-2 transition-colors"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 2l8 8M10 2l-8 8" /></svg>
              </button>
            </div>

            {/* Body */}
            <div className="p-6">
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
          </div>
        </div>
      )}

      {/* Knowledge */}
      <div className="mb-[22px]">
        <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-2 px-[22px] pb-2 font-medium">
          Knowledge
        </div>
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
      </div>

      {/* Knowledge modal */}
      {knowledgeModal && (
        <div
          className="fixed inset-0 bg-black/30 backdrop-blur-[4px] z-50 flex items-center justify-center"
          onClick={() => setKnowledgeModal(null)}
        >
          <div
            className="bg-white rounded-[14px] border border-rule shadow-[0_12px_40px_rgba(20,19,42,0.15)] max-w-[560px] w-full mx-4 max-h-[70vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}
            style={{ animation: "fadeUp 0.25s ease-out both" }}
          >
            <div className="px-6 pt-6 pb-4 border-b border-rule flex items-center justify-between">
              <h3 className="text-[18px] font-medium text-ink tracking-[-0.01em]" style={{ fontFamily: "var(--font-display)" }}>
                {knowledgeModal === "methodology" ? "Research Methodology" : "Agent Memory"}
              </h3>
              <button
                onClick={() => setKnowledgeModal(null)}
                className="w-7 h-7 rounded-full flex items-center justify-center text-muted hover:text-ink hover:bg-paper-2 transition-colors"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 2l8 8M10 2l-8 8" /></svg>
              </button>
            </div>
            <div className="p-6">
              {knowledgeModal === "methodology" ? (
                <div className="space-y-3">
                  {methodologySteps.map(step => (
                    <div key={step.id} className="flex gap-3">
                      <div className="w-6 h-6 rounded-full bg-gradient-to-r from-purple to-pink text-white text-[10px] font-mono font-bold flex items-center justify-center shrink-0 mt-0.5">
                        {step.id}
                      </div>
                      <div>
                        <div className="text-[13px] font-medium text-ink">{step.name}</div>
                        <div className="text-[12px] text-muted leading-[1.5] mt-0.5">{step.description.slice(0, 150)}{step.description.length > 150 ? "..." : ""}</div>
                        <div className="font-mono text-[9px] text-purple uppercase tracking-[0.08em] mt-1">{step.agent_action}</div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <div className="text-[36px] mb-2" style={{ fontFamily: "var(--font-display)" }}>
                    {memoryCount > 0 ? memoryCount : 0}
                  </div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted mb-4">
                    Preferences learned from past runs
                  </div>
                  <p className="text-[13px] text-muted leading-[1.5] max-w-[360px] mx-auto">
                    {memoryCount > 0
                      ? "The agent remembers your preferences from past runs and uses them to improve future analyses."
                      : "As you run analyses, the agent will learn your preferences for report types, design themes, and refinement patterns."
                    }
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

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
