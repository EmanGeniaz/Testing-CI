"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { listSkills, uploadSkill, type SkillInfo } from "../lib/api";

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

  useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

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

      {/* Knowledge */}
      <div className="mb-[22px]">
        <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-2 px-[22px] pb-2 font-medium">
          Knowledge
        </div>
        {["Methodology", "Memory"].map(item => (
          <div key={item} className="py-1.5 px-[22px] text-[13px] text-ink-3 flex items-center gap-[11px] cursor-pointer hover:text-ink transition-colors">
            <svg className="w-[14px] h-[14px] opacity-60" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
              <path d="M2 4h12 M2 8h12 M2 12h12"/>
            </svg>
            {item}
          </div>
        ))}
      </div>

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
