"use client";

import { useState } from "react";
import AgentInspectorModal, { type AgentOption } from "./AgentInspectorModal";

interface StudioViewProps {
  onSessionReady: (sid: string, filename: string, cols: string[], rowCount: number) => void;
  onViewReport: () => void;
  sessionId: string | null;
}

const AGENTS: AgentOption[] = [
  {
    id: "explainable_ai_tagging",
    name: "Brand Insights",
    description: "Brand health, perception tracking, equity analysis",
    initials: "BI",
    gradient: "linear-gradient(135deg, #6c4cff 0%, #a899ff 100%)",
  },
  {
    id: "category_insights",
    name: "Category Insights",
    description: "Market trends, dynamics, growth signals",
    initials: "CI",
    gradient: "linear-gradient(135deg, #4d8cff 0%, #99bfff 100%)",
  },
  {
    id: "competitive_intelligence",
    name: "Competitive Intelligence",
    description: "Head-to-head positioning, share of voice",
    initials: "CO",
    gradient: "linear-gradient(135deg, #ff4d8d 0%, #ff99bd 100%)",
  },
  {
    id: "issues_crisis",
    name: "Issues & Crisis",
    description: "Risk signals, narrative tracking, reputation",
    initials: "IC",
    gradient: "linear-gradient(135deg, #d4a017 0%, #f0d060 100%)",
  },
  {
    id: "pharma_social_intelligence",
    name: "Pharma Social Intelligence",
    description: "Patient journey, HCP sentiment, disease-area",
    initials: "PS",
    gradient: "linear-gradient(135deg, #18a957 0%, #60e090 100%)",
  },
  {
    id: "genz_brand_tracker",
    name: "Gen Z Brand Tracker",
    description: "Youth culture, platform trends, value alignment",
    initials: "GZ",
    gradient: "linear-gradient(135deg, #ff4d8d 0%, #6c4cff 100%)",
  },
];

export default function StudioView({ onSessionReady, onViewReport }: StudioViewProps) {
  const [activeAgent, setActiveAgent] = useState<AgentOption | null>(null);

  return (
    <div className="px-12 py-14 max-w-[1280px]" style={{ animation: "fadeUp 0.6s cubic-bezier(0.2, 0.7, 0.2, 1) both" }}>
      {/* Hero */}
      <header className="mb-7">
        <div className="font-mono text-[11px] uppercase tracking-[0.18em] mb-3 gradient-text-subtle font-medium">
          — Consumer Intelligence Studio
        </div>
        <h1
          className="text-[48px] leading-[1] tracking-[-0.03em] font-normal text-ink mb-3"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Pick an{" "}
          <em
            className="gradient-text"
            style={{ fontStyle: "italic", WebkitTextFillColor: "transparent" }}
          >
            agent
          </em>
        </h1>
        <p
          className="text-[17px] leading-[1.4] text-muted font-light max-w-[600px]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Each agent uses a different skill and methodology. Pick one, or create your own.
        </p>
      </header>

      {/* Agent grid */}
      <div className="grid grid-cols-3 gap-[14px] max-w-[1100px]">
        {AGENTS.map(agent => (
          <button
            key={agent.id}
            onClick={() => setActiveAgent(agent)}
            className="text-left bg-white border border-rule rounded-[12px] p-[18px] cursor-pointer transition-all hover:-translate-y-[2px] hover:border-purple-rule"
            style={{ boxShadow: "0 1px 2px rgba(20,19,42,0.04)" }}
            onMouseEnter={e => (e.currentTarget.style.boxShadow = "0 8px 24px rgba(108,76,255,0.1)")}
            onMouseLeave={e => (e.currentTarget.style.boxShadow = "0 1px 2px rgba(20,19,42,0.04)")}
          >
            <div
              className="w-9 h-9 rounded-[10px] flex items-center justify-center font-mono text-[12px] font-semibold text-white mb-3"
              style={{ background: agent.gradient }}
            >
              {agent.initials}
            </div>
            <div className="text-[15px] font-semibold text-ink mb-1">{agent.name}</div>
            <div className="text-[12px] text-muted leading-[1.45]">{agent.description}</div>
          </button>
        ))}

        {/* Create Your Own card — full row */}
        <button
          onClick={() => {
            const custom: AgentOption = {
              id: "custom",
              name: "Custom Agent",
              description: "Custom prompt and methodology",
              initials: "+",
              gradient: "linear-gradient(135deg, #6c4cff, #ff4d8d)",
            };
            setActiveAgent(custom);
          }}
          className="col-span-3 text-left rounded-[12px] p-[18px] cursor-pointer transition-all hover:bg-purple-soft/40"
          style={{
            border: "2px dashed var(--color-rule-2)",
            background: "transparent",
          }}
        >
          <div className="flex items-center gap-4">
            <div
              className="w-9 h-9 rounded-[10px] flex items-center justify-center shrink-0"
              style={{
                background:
                  "linear-gradient(135deg, rgba(108,76,255,0.08), rgba(255,77,141,0.08))",
                border: "2px dashed var(--color-purple-3)",
              }}
            >
              <svg
                width="16"
                height="16"
                fill="none"
                stroke="var(--color-purple)"
                strokeWidth="2"
                viewBox="0 0 24 24"
              >
                <path d="M12 5v14m-7-7h14" strokeLinecap="round" />
              </svg>
            </div>
            <div className="min-w-0">
              <div
                className="text-[15px] font-semibold mb-0.5 gradient-text"
                style={{ WebkitTextFillColor: "transparent" }}
              >
                Create Your Own
              </div>
              <div className="text-[12px] text-muted leading-[1.45]">
                Custom agent with your own prompt and methodology
              </div>
            </div>
          </div>
        </button>
      </div>

      {/* Modal */}
      {activeAgent && (
        <AgentInspectorModal
          agent={activeAgent}
          onClose={() => setActiveAgent(null)}
          onSessionReady={onSessionReady}
          onViewReport={() => {
            setActiveAgent(null);
            onViewReport();
          }}
        />
      )}
    </div>
  );
}
