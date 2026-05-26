"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { uploadFile, setContext, setSchema, runTagging, getReportTypes, getStatus, getResults, refineReport, listTemplates, type ReportTypeInfo, type TemplateInfo } from "../lib/api";

interface StudioViewProps {
  onSessionReady: (sid: string, filename: string, cols: string[], rowCount: number) => void;
  onViewReport: () => void;
  sessionId: string | null;
}

type Phase = "select-agent" | "data-sources" | "configure" | "running" | "report";

interface AgentOption {
  id: string;
  name: string;
  description: string;
  initials: string;
  gradient: string;
}

const AGENTS: AgentOption[] = [
  { id: "explainable_ai_tagging", name: "Brand Insights", description: "Brand health, perception tracking, equity analysis", initials: "BI", gradient: "linear-gradient(135deg, #6c4cff 0%, #a899ff 100%)" },
  { id: "category_insights", name: "Category Insights", description: "Market trends, category dynamics, growth signals", initials: "CI", gradient: "linear-gradient(135deg, #4d8cff 0%, #99bfff 100%)" },
  { id: "competitive_intelligence", name: "Competitive Intelligence", description: "Head-to-head positioning, share of voice, threat analysis", initials: "CO", gradient: "linear-gradient(135deg, #ff4d8d 0%, #ff99bd 100%)" },
  { id: "issues_crisis", name: "Issues & Crisis", description: "Risk signals, narrative tracking, reputation monitoring", initials: "IC", gradient: "linear-gradient(135deg, #d4a017 0%, #f0d060 100%)" },
  { id: "pharma_social_intelligence", name: "Pharma Social Intelligence", description: "Patient journey, HCP sentiment, disease-area insights", initials: "PS", gradient: "linear-gradient(135deg, #18a957 0%, #60e090 100%)" },
  { id: "genz_brand_tracker", name: "Gen Z Brand Tracker", description: "Youth culture signals, platform trends, value alignment", initials: "GZ", gradient: "linear-gradient(135deg, #ff4d8d 0%, #6c4cff 100%)" },
];

interface DataSourceOption {
  id: string;
  name: string;
  category: string;
  available: boolean;
}

const DATA_SOURCES: { category: string; sources: DataSourceOption[] }[] = [
  {
    category: "Social Listening Platforms",
    sources: [
      { id: "brandwatch", name: "Brandwatch", category: "social_listening", available: false },
      { id: "meltwater", name: "Meltwater", category: "social_listening", available: false },
      { id: "sprinklr", name: "Sprinklr", category: "social_listening", available: false },
      { id: "talkwalker", name: "Talkwalker", category: "social_listening", available: false },
    ],
  },
  {
    category: "Social Media Direct",
    sources: [
      { id: "reddit_api", name: "Reddit API", category: "social_direct", available: false },
      { id: "twitter_api", name: "X / Twitter API", category: "social_direct", available: false },
      { id: "meta_api", name: "Meta API", category: "social_direct", available: false },
    ],
  },
  {
    category: "InfoVision API",
    sources: [
      { id: "infovision", name: "InfoVision API", category: "infovision", available: false },
    ],
  },
  {
    category: "Traditional Media",
    sources: [
      { id: "news_api", name: "News API", category: "traditional", available: false },
      { id: "print_archives", name: "Print Archives", category: "traditional", available: false },
    ],
  },
];

interface ThinkingStep {
  time: string;
  text: string;
  meta: string;
  status: "active" | "done";
}

interface ReportData {
  title: string;
  subtitle: string;
  metadata: Record<string, string | number>;
  sections: { id: string; heading: string; body: string }[];
  findings: { number: number; confidence: string; claim: string; support: string }[];
  evidence: { source: string; quote: string; tags: string[]; sentiment: string }[];
  so_what: string;
}

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function StudioView({ onSessionReady, onViewReport, sessionId: existingSession }: StudioViewProps) {
  const [phase, setPhase] = useState<Phase>("select-agent");
  const [prompt, setPrompt] = useState("");

  // Agent selection state
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [customAgentPrompt, setCustomAgentPrompt] = useState("");

  // Data sources state
  const [selectedDataSources, setSelectedDataSources] = useState<string[]>([]);
  const [contextBrief, setContextBrief] = useState("");

  // Upload state
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(existingSession);
  const [columns, setColumns] = useState<string[]>([]);
  const [rowCount, setRowCount] = useState(0);
  const [dragging, setDragging] = useState(false);

  // Config state
  const [primaryCol, setPrimaryCol] = useState("");
  const [reportTypes, setReportTypes] = useState<ReportTypeInfo[]>([]);
  const [reportType, setReportType] = useState("");
  const [provider, setProvider] = useState("claude");
  const [error, setError] = useState("");

  // Thinking state
  const [steps, setSteps] = useState<ThinkingStep[]>([]);
  const [progress, setProgress] = useState(0);
  const [analyzedRows, setAnalyzedRows] = useState(0);

  // Report state
  const [report, setReport] = useState<ReportData | null>(null);
  const [taggedData, setTaggedData] = useState<Record<string, unknown>[]>([]);

  // Refine panel state
  const [refineFeedback, setRefineFeedback] = useState("");
  const [refineDesignTheme, setRefineDesignTheme] = useState("default");
  const [refining, setRefining] = useState(false);

  // Template selection state
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);

  // Tooltip state for coming-soon sources
  const [hoveredSource, setHoveredSource] = useState<string | null>(null);

  const thinkingRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getReportTypes()
      .then(res => { setReportTypes(res.report_types); setReportType(res.default); })
      .catch(() => {});
    listTemplates()
      .then(res => { setTemplates(res.templates); })
      .catch(() => {});
  }, []);

  const addStep = useCallback((text: string, meta: string) => {
    const now = new Date();
    const time = `${String(now.getMinutes()).padStart(2,"0")}:${String(now.getSeconds()).padStart(2,"0")}`;
    setSteps(prev => {
      const updated = prev.map(s => ({ ...s, status: "done" as const }));
      return [...updated, { time, text, meta, status: "active" as const }];
    });
  }, []);

  const handleFile = useCallback(async (f: File) => {
    setFile(f);
    setError("");
    setUploading(true);
    try {
      const res = await uploadFile(f);
      setColumns(res.columns);
      setRowCount(res.row_count);
      setSessionId(res.session_id);
      const defaultPrimary = res.columns.find((c: string) => /detail|text|content|body|description|review/i.test(c)) || res.columns[0];
      setPrimaryCol(defaultPrimary);
      if (!selectedDataSources.includes("file_upload")) {
        setSelectedDataSources(prev => [...prev, "file_upload"]);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, [selectedDataSources]);

  const toggleDataSource = useCallback((id: string) => {
    setSelectedDataSources(prev =>
      prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]
    );
  }, []);

  const handleRun = async () => {
    if (!sessionId || !primaryCol) return;
    setError("");
    setPhase("running");
    setSteps([]);
    setProgress(0);
    setAnalyzedRows(0);

    const agentLabel = selectedAgent === "custom"
      ? "Custom Agent"
      : AGENTS.find(a => a.id === selectedAgent)?.name || selectedAgent || "";

    const templateHint = selectedTemplateId
      ? `Use template: ${selectedTemplateId}`
      : "";

    const userPrompt = [
      contextBrief,
      customAgentPrompt,
      prompt,
      selectedAgent && selectedAgent !== "custom" ? `Use the ${agentLabel} skill.` : "",
      templateHint,
    ].filter(Boolean).join("\n\n");

    onSessionReady(sessionId, file?.name || "dataset", columns, rowCount);

    try {
      const res = await fetch(`${BASE}/orchestrate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, prompt: userPrompt, provider }),
      });

      if (!res.ok || !res.body) {
        throw new Error("Orchestrator unavailable");
      }

      // Side-channel: poll session status for progress while orchestrator runs
      let progressPollActive = true;
      const pollProgress = async () => {
        while (progressPollActive) {
          await new Promise(r => setTimeout(r, 4000));
          if (!progressPollActive) break;
          try {
            const st = await getStatus(sessionId);
            if (st.progress > 0) setProgress(st.progress);
            if (st.analyzed_rows > 0) setAnalyzedRows(st.analyzed_rows);
          } catch { /* ignore */ }
        }
      };
      pollProgress();

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) { progressPollActive = false; break; }
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const event = JSON.parse(line);
            if (event.type === "thinking") {
              addStep(event.text, "reasoning");
            } else if (event.type === "tool_call") {
              const argsHint = event.args?.report_type_id || event.args?.text_column || "";
              addStep(`Calling ${event.tool}${argsHint ? ` (${argsHint})` : ""}`, "tool");
            } else if (event.type === "tool_result") {
              const summary = typeof event.result === "string"
                ? event.result.slice(0, 120)
                : JSON.stringify(event.result).slice(0, 120);
              addStep(`${event.tool} → ${summary}...`, "result");
            } else if (event.type === "progress") {
              setProgress(event.progress ?? 0);
              setAnalyzedRows(event.analyzed_rows ?? 0);
            } else if (event.type === "complete") {
              if (event.report) setReport(event.report);
              addStep(event.summary || "Agent complete", "done");
              const results = await getResults(sessionId);
              setTaggedData(results.analyzed_data ?? []);
              setTimeout(() => setPhase("report"), 800);
            } else if (event.type === "error") {
              addStep(`Error: ${event.message || event.text || "Unknown"}`, "error");
            }
          } catch {
            // skip malformed JSON lines
          }
        }
      }
    } catch {
      // Fallback to the old hardcoded pipeline if orchestrator is unavailable
      addStep(`Falling back to direct pipeline for ${agentLabel}`, "fallback");
      try {
        const additionalContext = [contextBrief, customAgentPrompt, prompt].filter(Boolean).join("\n\n");
        await setContext({ session_id: sessionId, dataset_type: "Single brand", focus_brand: "", additional_context: additionalContext });
        await setSchema({ session_id: sessionId, primary_text_column: primaryCol, visible_columns: columns, ai_columns: [primaryCol] });
        const backendReportTypes = reportTypes.map(rt => rt.id);
        const effectiveReportType = selectedAgent && selectedAgent !== "custom" && backendReportTypes.includes(selectedAgent)
          ? selectedAgent : reportType;
        await runTagging({ session_id: sessionId, provider, report_type: effectiveReportType });
        addStep(`Tagging started — ${provider} / ${effectiveReportType}`, "agent");
        pollStatus(sessionId);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to start");
        setPhase("select-agent");
      }
    }
  };

  const pollStatus = useCallback(async (sid: string) => {
    const poll = async () => {
      try {
        const st = await getStatus(sid);
        setProgress(st.progress ?? 0);
        setAnalyzedRows(st.analyzed_rows ?? 0);

        if (st.analyzed_rows > 0 && st.analyzed_rows % 5 === 0) {
          addStep(`Tagged ${st.analyzed_rows} of ${st.total_rows ?? rowCount} rows`, "tagging");
        }

        if (st.status === "complete") {
          addStep("Tagging complete", "done");
          const res = await getResults(sid);
          setTaggedData(res.analyzed_data ?? []);
          addStep(`${(res.analyzed_data ?? []).length} rows tagged — generating report`, "report");

          try {
            const reportRes = await fetch(`${BASE}/session/${sid}/generate-report`, { method: "POST" });
            if (reportRes.ok) {
              const reportData = await reportRes.json();
              setReport(reportData);
              addStep("Report generated", "done");
            }
          } catch {
            // Report generation not available — still show results
          }

          setTimeout(() => setPhase("report"), 1000);
          return;
        }

        if (st.status === "error") {
          addStep(`Error: ${st.error_message || "Unknown error"}`, "error");
          setError(st.error_message || "Tagging failed");
          return;
        }

        setTimeout(poll, 3000);
      } catch {
        setTimeout(poll, 5000);
      }
    };
    poll();
  }, [addStep, rowCount]);

  const handleRefine = async () => {
    if (!sessionId || !refineFeedback.trim()) return;
    setRefining(true);
    addStep("Refining report based on feedback...", "refine");
    try {
      const updatedReport = await refineReport(sessionId, refineFeedback, refineDesignTheme);
      if (updatedReport && updatedReport.title) {
        setReport(updatedReport);
      }
      setRefineFeedback("");
      addStep("Report refined successfully", "done");
    } catch {
      addStep("Refinement failed — original report preserved", "error");
    } finally {
      setRefining(false);
    }
  };

  // Step 1: Agent Selection phase
  if (phase === "select-agent") {
    return (
      <div className="px-12 py-14 max-w-[1280px]" style={{ animation: "fadeUp 0.7s cubic-bezier(0.2, 0.7, 0.2, 1) both" }}>
        {/* Hero */}
        <header className="mb-11">
          <div className="font-mono text-[11px] uppercase tracking-[0.18em] mb-[22px] inline-flex items-center gap-[10px] gradient-text-subtle font-medium">
            <span className="w-5 h-[1px] bg-gradient-to-r from-purple to-pink inline-block" />
            Consumer Intelligence Studio
          </div>
          <h1 className="text-[52px] leading-[1] tracking-[-0.035em] font-normal text-ink mb-[18px] max-w-[820px]"
            style={{ fontFamily: "var(--font-display)" }}>
            Choose your <em className="gradient-text" style={{ fontStyle: "italic", WebkitTextFillColor: "transparent" }}>agent</em>
          </h1>
          <p className="text-[18px] leading-[1.5] text-muted font-light max-w-[640px] tracking-[-0.01em]"
            style={{ fontFamily: "var(--font-display)" }}>
            Select a pre-configured analysis agent, or create your own with a custom prompt and methodology.
          </p>
        </header>

        {/* Step indicator */}
        <div className="flex items-center gap-3 mb-8">
          {[
            { num: "01", label: "Agent", active: true },
            { num: "02", label: "Data Sources", active: false },
            { num: "03", label: "Configure", active: false },
          ].map((step, i) => (
            <div key={step.num} className="flex items-center gap-3">
              {i > 0 && <span className="w-8 h-px bg-rule" />}
              <span className={`font-mono text-[10px] uppercase tracking-[0.14em] font-medium ${step.active ? "text-purple" : "text-muted-2"}`}>
                <span className={step.active ? "gradient-text-subtle" : ""}>{step.num}</span>
                <span className="ml-1.5">{step.label}</span>
              </span>
            </div>
          ))}
        </div>

        {/* Agent cards grid */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          {AGENTS.map(agent => (
            <button
              key={agent.id}
              onClick={() => setSelectedAgent(agent.id)}
              className="relative text-left bg-white border rounded-[12px] p-5 transition-all cursor-pointer group"
              style={{
                borderColor: selectedAgent === agent.id ? "var(--color-purple)" : "var(--color-rule)",
                borderLeftWidth: selectedAgent === agent.id ? "3px" : "1px",
                borderImage: selectedAgent === agent.id ? "linear-gradient(180deg, var(--color-purple), var(--color-pink)) 1" : "none",
                boxShadow: selectedAgent === agent.id
                  ? "0 4px 20px rgba(108, 76, 255, 0.15)"
                  : "0 1px 2px rgba(20, 19, 42, 0.04)",
                transform: selectedAgent === agent.id ? "translateY(-1px)" : "none",
              }}
            >
              <div className="flex items-start gap-4">
                {/* Icon circle */}
                <div className="w-11 h-11 rounded-full flex items-center justify-center text-white text-[13px] font-mono font-bold tracking-wide shrink-0"
                  style={{ background: agent.gradient }}>
                  {agent.initials}
                </div>
                <div className="min-w-0">
                  <div className="text-[16px] font-medium text-ink mb-1 tracking-[-0.01em]"
                    style={{ fontFamily: "var(--font-display)" }}>
                    {agent.name}
                  </div>
                  <div className="text-[13px] text-muted leading-[1.4]">
                    {agent.description}
                  </div>
                </div>
                {/* Checkmark */}
                {selectedAgent === agent.id && (
                  <div className="ml-auto shrink-0 w-6 h-6 rounded-full bg-gradient-to-r from-purple to-pink flex items-center justify-center">
                    <svg width="12" height="12" fill="none" stroke="white" strokeWidth="2.5" viewBox="0 0 12 12">
                      <path d="M2.5 6.5L5 9l4.5-6" />
                    </svg>
                  </div>
                )}
              </div>
            </button>
          ))}
        </div>

        {/* Create Your Own card — special styling */}
        <button
          onClick={() => setSelectedAgent("custom")}
          className="relative w-full text-left rounded-[12px] p-5 transition-all cursor-pointer group"
          style={{
            border: selectedAgent === "custom" ? "2px solid var(--color-purple)" : "2px dashed var(--color-rule-2)",
            background: selectedAgent === "custom" ? "var(--color-purple-soft)" : "transparent",
            boxShadow: selectedAgent === "custom" ? "0 4px 20px rgba(108, 76, 255, 0.15)" : "none",
          }}
        >
          <div className="flex items-start gap-4">
            <div className="w-11 h-11 rounded-full flex items-center justify-center shrink-0"
              style={{
                border: "2px dashed var(--color-purple-3)",
                background: "linear-gradient(135deg, rgba(108,76,255,0.08), rgba(255,77,141,0.08))",
              }}>
              <svg width="18" height="18" fill="none" stroke="var(--color-purple)" strokeWidth="2" viewBox="0 0 24 24">
                <path d="M12 5v14m-7-7h14" strokeLinecap="round" />
              </svg>
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[16px] font-medium tracking-[-0.01em] mb-1 gradient-text"
                style={{ fontFamily: "var(--font-display)", WebkitTextFillColor: "transparent" }}>
                Create Your Own
              </div>
              <div className="text-[13px] text-muted leading-[1.4]">
                Custom agent with your own prompt and methodology
              </div>
            </div>
            {selectedAgent === "custom" && (
              <div className="ml-auto shrink-0 w-6 h-6 rounded-full bg-gradient-to-r from-purple to-pink flex items-center justify-center">
                <svg width="12" height="12" fill="none" stroke="white" strokeWidth="2.5" viewBox="0 0 12 12">
                  <path d="M2.5 6.5L5 9l4.5-6" />
                </svg>
              </div>
            )}
          </div>
        </button>

        {/* Custom agent prompt input */}
        {selectedAgent === "custom" && (
          <div className="mt-4 bg-white border border-rule rounded-[12px] p-5 shadow-[0_1px_2px_rgba(20,19,42,0.04)]"
            style={{ animation: "fadeUp 0.3s ease-out both" }}>
            <label className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted font-medium block mb-2">
              Custom Agent Prompt
            </label>
            <textarea
              className="w-full bg-paper border border-rule rounded-[8px] px-4 py-3 text-[15px] leading-[1.5] text-ink outline-none resize-none transition-all focus:border-purple focus:shadow-[0_0_0_3px_var(--color-purple-soft)] placeholder:text-muted-2 placeholder:italic"
              style={{ fontFamily: "var(--font-display)" }}
              rows={3}
              placeholder="Describe the analysis methodology, what signals to look for, and how to structure the output..."
              value={customAgentPrompt}
              onChange={e => setCustomAgentPrompt(e.target.value)}
            />
          </div>
        )}

        {/* Continue button */}
        <div className="flex items-center justify-between mt-8 pt-6 border-t border-rule">
          <div className="font-mono text-[11px] text-muted-2 uppercase tracking-[0.1em]">
            {selectedAgent ? (
              <span className="text-purple font-medium">
                {selectedAgent === "custom" ? "Custom Agent" : AGENTS.find(a => a.id === selectedAgent)?.name} selected
              </span>
            ) : (
              "Select an agent to continue"
            )}
          </div>
          <button
            onClick={() => { if (selectedAgent) setPhase("data-sources"); }}
            disabled={!selectedAgent}
            className="btn-gradient disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-none"
          >
            <span>Continue to data sources</span>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 6h8 M6 2l4 4-4 4"/></svg>
          </button>
        </div>
      </div>
    );
  }

  // Step 2: Data Sources phase
  if (phase === "data-sources") {
    return (
      <div className="px-12 py-14 max-w-[1280px]" style={{ animation: "fadeUp 0.6s cubic-bezier(0.2, 0.7, 0.2, 1) both" }}>
        <header className="mb-8">
          <div className="font-mono text-[11px] uppercase tracking-[0.18em] mb-[22px] inline-flex items-center gap-[10px] gradient-text-subtle font-medium">
            <span className="w-5 h-[1px] bg-gradient-to-r from-purple to-pink inline-block" />
            Consumer Intelligence Studio
          </div>
          <h1 className="text-[44px] leading-[1] tracking-[-0.035em] font-normal text-ink mb-[14px] max-w-[820px]"
            style={{ fontFamily: "var(--font-display)" }}>
            Connect your <em className="gradient-text" style={{ fontStyle: "italic", WebkitTextFillColor: "transparent" }}>data</em>
          </h1>
          <p className="text-[17px] leading-[1.5] text-muted font-light max-w-[640px] tracking-[-0.01em]"
            style={{ fontFamily: "var(--font-display)" }}>
            Upload files or connect to listening platforms. Multiple sources can be combined.
          </p>
        </header>

        {/* Step indicator */}
        <div className="flex items-center gap-3 mb-8">
          {[
            { num: "01", label: "Agent", active: false, done: true },
            { num: "02", label: "Data Sources", active: true, done: false },
            { num: "03", label: "Configure", active: false, done: false },
          ].map((step, i) => (
            <div key={step.num} className="flex items-center gap-3">
              {i > 0 && <span className="w-8 h-px bg-rule" />}
              <span className={`font-mono text-[10px] uppercase tracking-[0.14em] font-medium ${step.active ? "text-purple" : step.done ? "text-green" : "text-muted-2"}`}>
                <span className={step.active ? "gradient-text-subtle" : ""}>{step.done ? "✓" : step.num}</span>
                <span className="ml-1.5">{step.label}</span>
              </span>
            </div>
          ))}
        </div>

        {/* Upload files section */}
        <div className="mb-8">
          <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted font-medium mb-3 flex items-center gap-2">
            <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
              <path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Upload Files
          </div>
          <div className="bg-white border border-rule rounded-[12px] p-5 shadow-[0_1px_2px_rgba(20,19,42,0.04)]">
            <div
              onDragOver={e => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={e => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
              onClick={() => document.getElementById("studio-file-input")?.click()}
              className={`flex flex-col items-center justify-center gap-3 py-8 rounded-xl border-2 border-dashed cursor-pointer transition-all
                ${dragging ? "border-purple bg-purple-soft" : "border-rule-2 hover:border-purple-rule hover:bg-paper-2"}`}
            >
              <input id="studio-file-input" type="file" className="hidden" accept=".csv,.xlsx,.xls,.json,.docx"
                onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
              {uploading ? (
                <div className="w-7 h-7 border-2 border-purple border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg className="w-7 h-7 text-muted-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                </svg>
              )}
              <p className="text-[13px] text-ink-3">{uploading ? "Uploading..." : "Drop a file here or click to browse"}</p>
              <div className="flex gap-1.5">
                {["xlsx","csv","json","docx"].map(f => (
                  <span key={f} className="font-mono text-[10px] uppercase px-2 py-0.5 bg-paper-2 rounded text-muted tracking-wide">{f}</span>
                ))}
              </div>
            </div>

            {file && columns.length > 0 && (
              <div className="mt-4 text-[13px] text-ink-3 flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-green flex items-center justify-center">
                  <svg width="10" height="10" fill="none" stroke="white" strokeWidth="2.5" viewBox="0 0 12 12"><path d="M2.5 6.5L5 9l4.5-6" /></svg>
                </span>
                <span className="font-mono text-[10px] uppercase px-1.5 py-0.5 rounded bg-purple-soft text-purple font-bold">
                  {file.name.split(".").pop()?.toUpperCase()}
                </span>
                <span className="font-medium">{file.name}</span>
                <span className="text-muted-2">{rowCount} rows &times; {columns.length} cols</span>
              </div>
            )}

            {error && (
              <div className="mt-3 text-[12px] text-pink bg-pink-soft border border-pink/20 px-3 py-2 rounded-lg">{error}</div>
            )}
          </div>
        </div>

        {/* Platform data sources */}
        {DATA_SOURCES.map(group => (
          <div key={group.category} className="mb-6">
            <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted font-medium mb-3 flex items-center gap-2">
              {group.category === "Social Listening Platforms" && (
                <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                  <path d="M12 21a9 9 0 100-18 9 9 0 000 18zm0-18v18m-9-9h18" strokeLinecap="round" />
                </svg>
              )}
              {group.category === "Social Media Direct" && (
                <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                  <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2m8-10a4 4 0 100-8 4 4 0 000 8zm11 4l-4.35-4.35M21 11a5 5 0 11-10 0 5 5 0 0110 0z" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
              {group.category === "InfoVision API" && (
                <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                  <path d="M13 10V3L4 14h7v7l9-11h-7z" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
              {group.category === "Traditional Media" && (
                <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                  <path d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V9a2 2 0 012-2h2a2 2 0 012 2v9a2 2 0 01-2 2h-2zM5 12h7m-7 4h7" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
              {group.category}
            </div>
            <div className={`grid gap-3 ${group.sources.length === 1 ? "grid-cols-1 max-w-[320px]" : group.sources.length <= 3 ? "grid-cols-3" : "grid-cols-4"}`}>
              {group.sources.map(source => (
                <div
                  key={source.id}
                  className="relative bg-white border border-rule rounded-[10px] p-4 transition-all"
                  style={{
                    opacity: source.available ? 1 : 0.65,
                    boxShadow: selectedDataSources.includes(source.id)
                      ? "0 4px 16px rgba(108, 76, 255, 0.12)"
                      : "0 1px 2px rgba(20, 19, 42, 0.04)",
                    borderColor: selectedDataSources.includes(source.id)
                      ? "var(--color-purple)"
                      : "var(--color-rule)",
                  }}
                  onMouseEnter={() => !source.available && setHoveredSource(source.id)}
                  onMouseLeave={() => setHoveredSource(null)}
                >
                  <div className="flex items-center justify-between">
                    <div className="text-[14px] font-medium text-ink tracking-[-0.01em]">
                      {source.name}
                    </div>
                    {!source.available && (
                      <svg width="14" height="14" fill="none" stroke="var(--color-muted-2)" strokeWidth="1.5" viewBox="0 0 24 24">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                        <path d="M7 11V7a5 5 0 0110 0v4" />
                      </svg>
                    )}
                  </div>
                  <button
                    onClick={() => source.available && toggleDataSource(source.id)}
                    disabled={!source.available}
                    className={`mt-3 w-full py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.1em] font-medium transition-all ${
                      source.available
                        ? selectedDataSources.includes(source.id)
                          ? "bg-purple text-white"
                          : "bg-paper-2 text-ink-3 border border-rule hover:border-purple-rule hover:text-purple"
                        : "bg-paper-2 text-muted-2 border border-rule cursor-not-allowed"
                    }`}
                  >
                    {source.available
                      ? selectedDataSources.includes(source.id) ? "Connected" : "Connect"
                      : "Coming soon"}
                  </button>

                  {/* Tooltip */}
                  {hoveredSource === source.id && !source.available && (
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 bg-ink text-white text-[11px] rounded-lg whitespace-nowrap z-10 shadow-lg"
                      style={{ animation: "fadeUp 0.15s ease-out both" }}>
                      Coming soon
                      <div className="absolute top-full left-1/2 -translate-x-1/2 w-2 h-2 bg-ink rotate-45 -mt-1" />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}

        {/* Context Brief */}
        <div className="mt-8 mb-6">
          <label className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted font-medium block mb-3 flex items-center gap-2">
            <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
              <path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Context Brief
          </label>
          <div className="bg-white border border-rule rounded-[12px] p-5 shadow-[0_1px_2px_rgba(20,19,42,0.04)]">
            <textarea
              className="w-full bg-transparent border border-rule rounded-[8px] px-4 py-3 text-[15px] leading-[1.5] text-ink outline-none resize-none transition-all focus:border-purple focus:shadow-[0_0_0_3px_var(--color-purple-soft)] placeholder:text-muted-2 placeholder:italic min-h-[100px]"
              style={{ fontFamily: "var(--font-display)" }}
              rows={4}
              placeholder="Describe what you need from this analysis... e.g., 'Compare brand perception of Liquid Death vs non-alc spirits over the last 60 days, focusing on Gen Z audiences on Reddit and TikTok'"
              value={contextBrief}
              onChange={e => setContextBrief(e.target.value)}
            />
          </div>
        </div>

        {/* Template Selection */}
        {templates.length > 0 && (
          <div className="mt-8 mb-6">
            <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted font-medium mb-3 flex items-center gap-2">
              <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                <path d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm0 8a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zm10-1h6v3h-6v-3z" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Report Template
            </div>
            <div className="grid grid-cols-3 gap-3">
              {/* Auto-select card */}
              <button
                onClick={() => setSelectedTemplateId(null)}
                className="relative text-left bg-white border rounded-[10px] p-4 transition-all cursor-pointer group"
                style={{
                  borderColor: selectedTemplateId === null ? "var(--color-purple)" : "var(--color-rule)",
                  borderLeftWidth: selectedTemplateId === null ? "3px" : "1px",
                  borderImage: selectedTemplateId === null ? "linear-gradient(180deg, var(--color-purple), var(--color-pink)) 1" : "none",
                  boxShadow: selectedTemplateId === null
                    ? "0 4px 16px rgba(108, 76, 255, 0.12)"
                    : "0 1px 2px rgba(20, 19, 42, 0.04)",
                }}
              >
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-[11px] font-mono font-bold shrink-0"
                    style={{ background: "linear-gradient(135deg, #6c4cff 0%, #ff4d8d 100%)" }}>
                    AI
                  </div>
                  <div className="min-w-0">
                    <div className="text-[14px] font-medium text-ink mb-0.5 tracking-[-0.01em]" style={{ fontFamily: "var(--font-display)" }}>
                      Auto-select
                    </div>
                    <div className="text-[12px] text-muted leading-[1.4]">
                      Agent picks the best template
                    </div>
                  </div>
                  {selectedTemplateId === null && (
                    <div className="ml-auto shrink-0 w-5 h-5 rounded-full bg-gradient-to-r from-purple to-pink flex items-center justify-center">
                      <svg width="10" height="10" fill="none" stroke="white" strokeWidth="2.5" viewBox="0 0 12 12"><path d="M2.5 6.5L5 9l4.5-6" /></svg>
                    </div>
                  )}
                </div>
              </button>

              {/* Template cards */}
              {templates.map(tpl => (
                <button
                  key={tpl.id}
                  onClick={() => setSelectedTemplateId(tpl.id)}
                  className="relative text-left bg-white border rounded-[10px] p-4 transition-all cursor-pointer group"
                  style={{
                    borderColor: selectedTemplateId === tpl.id ? "var(--color-purple)" : "var(--color-rule)",
                    borderLeftWidth: selectedTemplateId === tpl.id ? "3px" : "1px",
                    borderImage: selectedTemplateId === tpl.id ? "linear-gradient(180deg, var(--color-purple), var(--color-pink)) 1" : "none",
                    boxShadow: selectedTemplateId === tpl.id
                      ? "0 4px 16px rgba(108, 76, 255, 0.12)"
                      : "0 1px 2px rgba(20, 19, 42, 0.04)",
                  }}
                >
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-full flex items-center justify-center text-[11px] font-mono font-bold shrink-0"
                      style={{
                        background: tpl.builtin
                          ? "linear-gradient(135deg, #4d8cff 0%, #99bfff 100%)"
                          : "linear-gradient(135deg, #18a957 0%, #60e090 100%)",
                        color: "white",
                      }}>
                      {tpl.name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase()}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-[14px] font-medium text-ink mb-0.5 tracking-[-0.01em]" style={{ fontFamily: "var(--font-display)" }}>
                        {tpl.name}
                      </div>
                      <div className="text-[12px] text-muted leading-[1.4] line-clamp-2">
                        {tpl.description}
                      </div>
                      {tpl.tags && tpl.tags.length > 0 && (
                        <div className="flex gap-1 flex-wrap mt-2">
                          {tpl.tags.slice(0, 3).map(tag => (
                            <span key={tag} className="font-mono text-[9px] lowercase px-[6px] py-[2px] rounded bg-paper-2 text-muted">
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    {selectedTemplateId === tpl.id && (
                      <div className="ml-auto shrink-0 w-5 h-5 rounded-full bg-gradient-to-r from-purple to-pink flex items-center justify-center">
                        <svg width="10" height="10" fill="none" stroke="white" strokeWidth="2.5" viewBox="0 0 12 12"><path d="M2.5 6.5L5 9l4.5-6" /></svg>
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="text-[12px] text-pink bg-pink-soft border border-pink/20 px-3 py-2 rounded-lg mb-4">{error}</div>
        )}

        {/* Navigation */}
        <div className="flex items-center justify-between mt-8 pt-6 border-t border-rule">
          <button onClick={() => setPhase("select-agent")} className="font-mono text-[11px] text-muted hover:text-ink transition-colors uppercase tracking-[0.1em]">
            &larr; Back to agents
          </button>
          <div className="flex items-center gap-4">
            {/* Summary */}
            <div className="font-mono text-[10px] text-muted-2 uppercase tracking-[0.1em]">
              {selectedDataSources.length > 0 || (file && columns.length > 0) ? (
                <span className="text-purple font-medium">
                  {(file && columns.length > 0 ? 1 : 0) + selectedDataSources.filter(s => s !== "file_upload").length} source(s) selected
                </span>
              ) : (
                "Upload a file to continue"
              )}
            </div>
            <button
              onClick={() => {
                if (file && columns.length > 0) {
                  setPrompt(contextBrief);
                  setPhase("configure");
                }
              }}
              disabled={!file || columns.length === 0}
              className="btn-gradient disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-none"
            >
              <span>Continue to configure</span>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 6h8 M6 2l4 4-4 4"/></svg>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Configure phase
  if (phase === "configure") {
    return (
      <div className="px-12 py-14 max-w-[900px]" style={{ animation: "fadeUp 0.5s ease-out both" }}>
        <div className="font-mono text-[11px] uppercase tracking-[0.18em] mb-3 gradient-text-subtle font-medium">
          Configure & Run
        </div>
        <h2 className="text-[36px] leading-[1] tracking-[-0.03em] font-normal text-ink mb-2"
          style={{ fontFamily: "var(--font-display)" }}>
          Set up your <em className="gradient-text" style={{ fontStyle: "italic", WebkitTextFillColor: "transparent" }}>analysis</em>
        </h2>
        <p className="text-[16px] text-muted font-light mb-8" style={{ fontFamily: "var(--font-display)" }}>
          {file?.name} — {rowCount} rows, {columns.length} columns
        </p>

        <div className="bg-white border border-rule rounded-[14px] p-7 shadow-[0_1px_2px_rgba(20,19,42,0.04)] space-y-6">
          {/* Primary text column */}
          <div>
            <label className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted font-medium block mb-2">
              Primary Text Column
            </label>
            <select value={primaryCol} onChange={e => setPrimaryCol(e.target.value)}
              className="w-full px-3 py-2.5 text-[14px] border border-rule rounded-[7px] bg-paper focus:border-purple focus:bg-white focus:shadow-[0_0_0_3px_var(--color-purple-soft)] outline-none transition-all">
              {columns.map(col => <option key={col} value={col}>{col}</option>)}
            </select>
          </div>

          {/* Report type + Provider */}
          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted font-medium block mb-2">Report Type</label>
              <select value={reportType} onChange={e => setReportType(e.target.value)}
                className="w-full px-3 py-2.5 text-[14px] border border-rule rounded-[7px] bg-paper focus:border-purple focus:bg-white focus:shadow-[0_0_0_3px_var(--color-purple-soft)] outline-none transition-all">
                {reportTypes.map(rt => <option key={rt.id} value={rt.id}>{rt.name}</option>)}
              </select>
            </div>
            <div>
              <label className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted font-medium block mb-2">AI Provider</label>
              <select value={provider} onChange={e => setProvider(e.target.value)}
                className="w-full px-3 py-2.5 text-[14px] border border-rule rounded-[7px] bg-paper focus:border-purple focus:bg-white focus:shadow-[0_0_0_3px_var(--color-purple-soft)] outline-none transition-all">
                {[
                  { id: "claude", label: "Claude (Anthropic)" },
                  { id: "gemini", label: "Gemini (Google)" },
                  { id: "openai", label: "OpenAI" },
                  { id: "groq", label: "Groq" },
                ].map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </div>
          </div>

          {/* Additional context */}
          {prompt && (
            <div>
              <label className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted font-medium block mb-2">
                Additional Context
              </label>
              <textarea value={prompt} onChange={e => setPrompt(e.target.value)}
                rows={2}
                className="w-full px-3 py-2.5 text-[14px] border border-rule rounded-[7px] bg-paper focus:border-purple focus:bg-white focus:shadow-[0_0_0_3px_var(--color-purple-soft)] outline-none transition-all resize-none"
                style={{ fontFamily: "var(--font-display)" }} />
            </div>
          )}

          {error && (
            <div className="text-[12px] text-pink bg-pink-soft border border-pink/20 px-3 py-2 rounded-lg">{error}</div>
          )}

          <div className="flex items-center justify-between pt-4 border-t border-rule">
            <button onClick={() => setPhase("data-sources")} className="font-mono text-[11px] text-muted hover:text-ink transition-colors uppercase tracking-[0.1em]">
              &larr; Back
            </button>
            <button onClick={handleRun} className="btn-gradient">
              <span>Run agent</span>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 6h8 M6 2l4 4-4 4"/></svg>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Running phase — thinking stream
  if (phase === "running") {
    return (
      <div className="px-12 py-14 max-w-[1280px]" style={{ animation: "fadeUp 0.6s cubic-bezier(0.2, 0.7, 0.2, 1) both" }}>
        <div className="flex items-baseline justify-between mb-[22px] pb-[14px] border-b border-rule">
          <h2 className="text-[26px] font-normal tracking-[-0.025em] text-ink" style={{ fontFamily: "var(--font-display)" }}>
            Agent <em className="gradient-text" style={{ fontStyle: "italic", WebkitTextFillColor: "transparent" }}>at work</em>
          </h2>
          <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted flex items-center gap-3.5">
            <span>RUN · {sessionId?.slice(0,8)}</span>
            <span className="flex items-center gap-1.5 text-purple font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-purple" style={{ animation: "blink 1.4s ease-in-out infinite" }} />
              Live
            </span>
          </div>
        </div>

        {/* Progress bar */}
        <div className="mb-6">
          <div className="h-1.5 bg-rule rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-purple to-pink rounded-full transition-all duration-700"
              style={{ width: `${progress}%` }} />
          </div>
          <div className="flex justify-between mt-2">
            <span className="font-mono text-[10px] text-muted">{analyzedRows} / {rowCount} rows</span>
            <span className="font-mono text-[10px] text-purple font-medium">{progress}%</span>
          </div>
        </div>

        {/* Thinking log */}
        <div ref={thinkingRef} className="font-mono text-[12px] leading-[1.75] p-5 bg-white border border-rule rounded-[10px] shadow-[0_1px_2px_rgba(20,19,42,0.03)] space-y-0.5">
          {steps.map((step, i) => (
            <div key={i} className="grid gap-3.5 items-baseline"
              style={{ gridTemplateColumns: "60px 22px 1fr auto", animation: "logIn 0.4s ease-out forwards" }}>
              <span className="text-muted-2 text-[11px]">{step.time}</span>
              <span className={`font-medium ${step.status === "done" ? "text-green" : "text-purple"}`}>
                {step.status === "done" ? "✓" : "→"}
              </span>
              <span className="text-ink-2">{step.text}</span>
              <span className="text-muted-2 text-[10px] uppercase tracking-[0.08em] px-[7px] py-px bg-paper-2 rounded">{step.meta}</span>
            </div>
          ))}
          {steps.length === 0 && (
            <div className="flex items-center gap-3 text-muted">
              <div className="w-4 h-4 border-2 border-purple border-t-transparent rounded-full animate-spin" />
              Initializing agent...
            </div>
          )}
        </div>
      </div>
    );
  }

  // Report phase
  return (
    <div className="px-12 py-14 max-w-[1280px]" style={{ animation: "fadeUp 0.7s cubic-bezier(0.2, 0.7, 0.2, 1) both" }}>
      {/* Report header */}
      <div className="font-mono text-[10px] uppercase tracking-[0.18em] mb-[18px] flex items-center gap-3.5 gradient-text-subtle font-medium">
        <span className="w-1.5 h-1.5 rounded-full bg-purple" style={{ animation: "blink 2s ease-in-out infinite" }} />
        <span>Draft · Awaiting review</span>
        <span className="flex-1 h-px bg-gradient-to-r from-purple-rule to-transparent" />
      </div>

      {report ? (
        <div className="grid gap-16" style={{ gridTemplateColumns: "1fr 340px" }}>
          {/* Main report */}
          <div className="min-w-0">
            <h1 className="text-[56px] leading-[1] tracking-[-0.035em] font-normal text-ink mb-4"
              style={{ fontFamily: "var(--font-display)" }}
              dangerouslySetInnerHTML={{ __html: report.title.replace(/\*([^*]+)\*/g, '<em class="gradient-text" style="font-style:italic;-webkit-text-fill-color:transparent">$1</em>') }} />

            <p className="text-[19px] leading-[1.5] text-muted font-light mb-5 max-w-[620px]"
              style={{ fontFamily: "var(--font-display)" }}>
              {report.subtitle}
            </p>

            {/* Export buttons row */}
            <div className="flex gap-2 mb-7">
              <a href={`${BASE}/session/${sessionId}/export/html-report`} target="_blank" rel="noopener noreferrer"
                className="px-4 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.1em] font-medium bg-gradient-to-r from-purple to-pink text-white shadow-[0_4px_12px_rgba(108,76,255,0.25)] hover:-translate-y-px hover:shadow-[0_6px_16px_rgba(108,76,255,0.35)] transition-all inline-flex items-center gap-2">
                <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M12 5v14m0 0l-4-4m4 4l4-4M4 19h16" strokeLinecap="round" strokeLinejoin="round" /></svg>
                Export HTML Report
              </a>
              <a href={`${BASE}/session/${sessionId}/export/pptx-report`} target="_blank" rel="noopener noreferrer"
                className="px-4 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.1em] font-medium bg-gradient-to-r from-purple to-pink text-white shadow-[0_4px_12px_rgba(108,76,255,0.25)] hover:-translate-y-px hover:shadow-[0_6px_16px_rgba(108,76,255,0.35)] transition-all inline-flex items-center gap-2">
                <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M12 5v14m0 0l-4-4m4 4l4-4M4 19h16" strokeLinecap="round" strokeLinejoin="round" /></svg>
                Export PPTX
              </a>
              <a href={`${BASE}/session/${sessionId}/export/csv`} target="_blank" rel="noopener noreferrer"
                className="px-4 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.1em] font-medium bg-transparent text-ink-3 border border-rule hover:text-purple hover:border-purple-rule hover:bg-purple-soft transition-all inline-flex items-center gap-2">
                <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M12 5v14m0 0l-4-4m4 4l4-4M4 19h16" strokeLinecap="round" strokeLinejoin="round" /></svg>
                Export CSV
              </a>
              <a href={`${BASE}/session/${sessionId}/export/xlsx`} target="_blank" rel="noopener noreferrer"
                className="px-4 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.1em] font-medium bg-transparent text-ink-3 border border-rule hover:text-purple hover:border-purple-rule hover:bg-purple-soft transition-all inline-flex items-center gap-2">
                <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M12 5v14m0 0l-4-4m4 4l4-4M4 19h16" strokeLinecap="round" strokeLinejoin="round" /></svg>
                Export XLSX
              </a>
            </div>

            {/* Metadata bar */}
            <div className="flex flex-wrap gap-6 py-4 px-5 border border-rule rounded-[10px] bg-white mb-10 font-mono text-[11px] text-ink-3 shadow-[0_1px_2px_rgba(20,19,42,0.04)]">
              {Object.entries(report.metadata)
                .filter(([key]) => {
                  const lower = key.toLowerCase();
                  return lower !== "llm_error" && lower !== "method" && lower !== "provider" && lower !== "generated_at" && lower !== "refine_error" && lower !== "refine_note" && lower !== "design_theme";
                })
                .map(([key, val]) => {
                  let displayVal = String(val ?? "");
                  // Truncate long values (e.g. period with repeated text)
                  if (displayVal.length > 80) {
                    const firstLine = displayVal.split("\n")[0];
                    displayVal = firstLine.length > 80 ? firstLine.slice(0, 77) + "..." : firstLine;
                  }
                  return (
                    <div key={key} className="flex flex-col gap-1">
                      <span className="text-muted-2 text-[9px] uppercase tracking-[0.12em]">{key.replace(/_/g, " ")}</span>
                      <span className="text-ink text-[12px] font-medium">{displayVal}</span>
                    </div>
                  );
                })}
            </div>

            {/* Sections */}
            {report.sections.map((sec, i) => (
              <div key={sec.id} className="bg-white border border-rule rounded-[12px] p-7 mb-4 shadow-[0_1px_3px_rgba(20,19,42,0.04)]">
                <h2 className="text-[28px] font-normal tracking-[-0.025em] text-ink mb-[18px] flex items-baseline gap-3.5"
                  style={{ fontFamily: "var(--font-display)" }}>
                  <span className="font-mono text-[11px] text-purple font-medium tracking-[0.08em]">{String(i+1).padStart(2,"0")}</span>
                  {sec.heading}
                </h2>
                <p className="text-[17px] leading-[1.65] text-ink-2 font-light max-w-[680px]"
                  style={{ fontFamily: "var(--font-display)" }}
                  dangerouslySetInnerHTML={{ __html: sec.body.replace(/\*\*([^*]+)\*\*/g, '<strong style="color:var(--color-ink);font-weight:500">$1</strong>') }} />
              </div>
            ))}

            {/* Findings */}
            {report.findings.length > 0 && (
              <h2 className="text-[28px] font-normal tracking-[-0.025em] text-ink mt-10 mb-[18px] flex items-baseline gap-3.5"
                style={{ fontFamily: "var(--font-display)" }}>
                <span className="font-mono text-[11px] text-purple font-medium tracking-[0.08em]">{String(report.sections.length + 1).padStart(2,"0")}</span>
                Key findings
              </h2>
            )}

            {report.findings.map(finding => (
              <div key={finding.number} className="bg-white border border-rule rounded-[12px] p-6 mb-3 shadow-[0_1px_3px_rgba(20,19,42,0.04)]">
                <div className="grid gap-[22px]" style={{ gridTemplateColumns: "80px 1fr" }}>
                  <div className="flex flex-col gap-2">
                    <div className="text-[42px] leading-[1] font-normal tracking-[-0.03em] gradient-text"
                      style={{ fontFamily: "var(--font-display)", WebkitTextFillColor: "transparent" }}>
                      {String(finding.number).padStart(2,"0")}
                    </div>
                    <span className={`font-mono text-[9px] uppercase tracking-[0.12em] inline-flex items-center gap-[5px] w-max px-2 py-[3px] rounded font-medium
                      ${finding.confidence === "high" ? "text-green bg-green-soft" : finding.confidence === "low" ? "text-pink bg-pink-soft" : "text-amber bg-amber-soft"}`}>
                      <span className={`w-[5px] h-[5px] rounded-full ${finding.confidence === "high" ? "bg-green" : finding.confidence === "low" ? "bg-pink" : "bg-amber"}`} />
                      {finding.confidence}
                    </span>
                  </div>
                  <div>
                    <div className="text-[23px] leading-[1.3] text-ink font-normal tracking-[-0.02em] mb-2.5"
                      style={{ fontFamily: "var(--font-display)" }}
                      dangerouslySetInnerHTML={{ __html: finding.claim.replace(/\*([^*]+)\*/g, '<em style="font-style:italic">$1</em>') }} />
                    <div className="text-[14px] leading-[1.65] text-muted">
                      {finding.support}
                    </div>
                  </div>
                </div>
              </div>
            ))}

            {/* So what */}
            {report.so_what && (
              <>
                <h2 className="text-[28px] font-normal tracking-[-0.025em] text-ink mt-10 mb-[18px] flex items-baseline gap-3.5"
                  style={{ fontFamily: "var(--font-display)" }}>
                  <span className="font-mono text-[11px] text-purple font-medium tracking-[0.08em]">{String(report.sections.length + 2).padStart(2,"0")}</span>
                  So what
                </h2>
                <div className="bg-white border border-rule rounded-[12px] p-7 shadow-[0_1px_3px_rgba(20,19,42,0.04)]">
                  <p className="text-[17px] leading-[1.65] text-ink-2 font-light max-w-[680px]"
                    style={{ fontFamily: "var(--font-display)" }}>
                    {report.so_what}
                  </p>
                </div>
              </>
            )}
          </div>

          {/* Evidence rail */}
          <aside className="sticky top-[90px] self-start border-l border-rule pl-7 max-h-[calc(100vh-130px)] overflow-y-auto">
            <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted mb-[18px] flex items-baseline justify-between font-medium">
              <span>Evidence</span>
              <span className="text-ink">{report.evidence.length} cited</span>
            </div>
            {report.evidence.map((ev, i) => (
              <div key={i} className="py-3.5 border-b border-rule last:border-b-0">
                <div className="font-mono text-[10px] text-muted uppercase tracking-[0.08em] mb-[7px] font-medium">
                  {ev.source}
                </div>
                <div className="text-[14px] leading-[1.55] text-ink-2 italic font-light mb-[9px]"
                  style={{ fontFamily: "var(--font-display)" }}>
                  &ldquo;{ev.quote}&rdquo;
                </div>
                <div className="flex gap-1 flex-wrap">
                  {ev.tags.map(tag => (
                    <span key={tag} className={`font-mono text-[9px] lowercase px-[7px] py-[2px] rounded
                      ${ev.sentiment === "positive" ? "text-green bg-green-soft" :
                        ev.sentiment === "negative" ? "text-pink bg-pink-soft" :
                        "text-muted bg-paper-2"}`}>
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </aside>
        </div>
      ) : (
        /* Fallback: show tagged data summary when report generation isn't available */
        <div>
          <h1 className="text-[42px] leading-[1] tracking-[-0.035em] font-normal text-ink mb-6"
            style={{ fontFamily: "var(--font-display)" }}>
            Analysis <em className="gradient-text" style={{ fontStyle: "italic", WebkitTextFillColor: "transparent" }}>complete</em>
          </h1>

            {(() => {
              const d = taggedData;
              const n = d.length;
              if (!n) return null;

              // Detect which fields exist in the data
              const hasField = (f: string) => d.some(r => r[f] != null && String(r[f]).trim() !== "");
              const countField = (f: string, v?: string) => v
                ? d.filter(r => String(r[f]) === v).length
                : d.filter(r => r[f] != null && String(r[f]).trim() !== "").length;
              const topValue = (f: string) => {
                const counts: Record<string, number> = {};
                d.forEach(r => { const v = String(r[f] ?? "").trim(); if (v) counts[v] = (counts[v] || 0) + 1; });
                const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
                return sorted[0] ? `${sorted[0][0]} (${Math.round(sorted[0][1] / n * 100)}%)` : "—";
              };

              // Build stats based on what fields exist
              const stats: { label: string; value: string | number; color: string }[] = [
                { label: "Total Rows", value: n, color: "text-ink" },
              ];

              if (hasField("sentiment")) {
                stats.push({ label: "Positive", value: `${Math.round(countField("sentiment", "Positive") / n * 100)}%`, color: "text-green" });
                stats.push({ label: "Negative", value: `${Math.round(countField("sentiment", "Negative") / n * 100)}%`, color: "text-pink" });
              }
              if (hasField("confidence")) {
                stats.push({ label: "Avg Confidence", value: `${Math.round(d.reduce((a, r) => a + (Number(r.confidence) || 0), 0) / n * 100)}%`, color: "text-purple" });
              }
              if (hasField("stage")) {
                stats.push({ label: "Top Stage", value: topValue("stage"), color: "text-purple" });
              }
              if (hasField("theme") || hasField("theme_pharma")) {
                const f = hasField("theme") ? "theme" : "theme_pharma";
                stats.push({ label: "Top Theme", value: topValue(f), color: "text-blue" });
              }
              if (hasField("unmet_need")) {
                stats.push({ label: "Unmet Needs Found", value: countField("unmet_need"), color: "text-pink" });
              }
              if (hasField("concern")) {
                stats.push({ label: "Concerns Found", value: countField("concern"), color: "text-amber" });
              }
              if (hasField("qol_impact")) {
                stats.push({ label: "QoL Impacts", value: countField("qol_impact"), color: "text-green" });
              }

              // If we still only have total rows (unknown schema), show generic field counts
              if (stats.length === 1) {
                const allKeys = new Set(d.flatMap(r => Object.keys(r)));
                stats.push({ label: "Fields per Row", value: allKeys.size, color: "text-purple" });
                const nonEmpty = d.filter(r => Object.values(r).some(v => v != null && String(v).trim() !== "")).length;
                stats.push({ label: "Non-empty Rows", value: `${Math.round(nonEmpty / n * 100)}%`, color: "text-green" });
              }

              return (
                <div className="grid gap-4 mb-8" style={{ gridTemplateColumns: `repeat(${Math.min(stats.length, 5)}, 1fr)` }}>
                  {stats.map(stat => (
                    <div key={stat.label} className="bg-white border border-rule rounded-xl p-5 text-center">
                      <div className={`text-[32px] font-normal tracking-[-0.03em] ${stat.color}`} style={{ fontFamily: "var(--font-display)" }}>
                        {stat.value}
                      </div>
                      <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted mt-1">{stat.label}</div>
                    </div>
                  ))}
                </div>
              );
            })()}

          <div className="flex gap-3 flex-wrap">
            <a href={`${BASE}/session/${sessionId}/export/html-report`} target="_blank" rel="noopener noreferrer" className="btn-gradient">
              <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M12 5v14m0 0l-4-4m4 4l4-4M4 19h16" strokeLinecap="round" strokeLinejoin="round" /></svg>
              <span>Export HTML Report</span>
            </a>
            <a href={`${BASE}/session/${sessionId}/export/pptx-report`} target="_blank" rel="noopener noreferrer"
              className="px-4 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.1em] font-medium bg-transparent text-ink-3 border border-rule hover:text-purple hover:border-purple-rule hover:bg-purple-soft transition-all inline-flex items-center gap-2">
              Export PPTX
            </a>
            <a href={`${BASE}/session/${sessionId}/export/csv`} target="_blank" rel="noopener noreferrer"
              className="px-4 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.1em] font-medium bg-transparent text-ink-3 border border-rule hover:text-purple hover:border-purple-rule hover:bg-purple-soft transition-all inline-flex items-center gap-2">
              Export CSV
            </a>
            <a href={`${BASE}/session/${sessionId}/export/xlsx`} target="_blank" rel="noopener noreferrer"
              className="px-4 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.1em] font-medium bg-transparent text-ink-3 border border-rule hover:text-purple hover:border-purple-rule hover:bg-purple-soft transition-all inline-flex items-center gap-2">
              Export XLSX
            </a>
            <button onClick={onViewReport} className="px-4 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.1em] font-medium bg-transparent text-ink-3 border border-rule hover:text-purple hover:border-purple-rule hover:bg-purple-soft transition-all">
              View in workbench
            </button>
            <button onClick={() => setPhase("select-agent")} className="font-mono text-[11px] text-muted hover:text-ink uppercase tracking-[0.1em] px-5 py-2.5 border border-rule rounded-lg hover:border-purple-rule transition-all">
              New report
            </button>
          </div>
        </div>
      )}

      {/* Action bar */}
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-white/92 backdrop-blur-[20px] border border-rule rounded-xl px-[18px] py-3 flex items-center gap-3 z-50 shadow-[0_12px_40px_rgba(108,76,255,0.15),0_2px_8px_rgba(20,19,42,0.08)]"
        style={{ animation: "barIn 0.5s 0.3s cubic-bezier(0.2, 0.7, 0.2, 1) both" }}>
        <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted pr-4 border-r border-rule font-medium">
          <span className="text-green">●</span> {report ? "Draft ready" : "Analysis complete"}
        </div>
        <button onClick={onViewReport} className="px-4 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.1em] font-medium bg-transparent text-ink-3 border border-rule hover:text-ink hover:border-purple-rule hover:bg-purple-soft transition-all">
          View data
        </button>
        <a href={`${BASE}/session/${sessionId}/export/html-report`} target="_blank" rel="noopener noreferrer"
          className="px-4 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.1em] font-medium bg-gradient-to-r from-purple to-pink text-white shadow-[0_4px_12px_rgba(108,76,255,0.25)] hover:-translate-y-px hover:shadow-[0_6px_16px_rgba(108,76,255,0.35)] transition-all no-underline">
          Export HTML Report
        </a>
        <a href={`${BASE}/session/${sessionId}/export/pptx-report`} target="_blank" rel="noopener noreferrer"
          className="px-4 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.1em] font-medium bg-gradient-to-r from-purple to-pink text-white shadow-[0_4px_12px_rgba(108,76,255,0.25)] hover:-translate-y-px hover:shadow-[0_6px_16px_rgba(108,76,255,0.35)] transition-all no-underline">
          Export PPTX
        </a>
        <a href={`${BASE}/session/${sessionId}/export/csv`} target="_blank" rel="noopener noreferrer"
          className="px-4 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.1em] font-medium bg-transparent text-ink-3 border border-rule hover:text-purple hover:border-purple-rule hover:bg-purple-soft transition-all no-underline">
          Export CSV
        </a>
        <a href={`${BASE}/session/${sessionId}/export/xlsx`} target="_blank" rel="noopener noreferrer"
          className="px-4 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.1em] font-medium bg-transparent text-ink-3 border border-rule hover:text-purple hover:border-purple-rule hover:bg-purple-soft transition-all no-underline">
          Export XLSX
        </a>
      </div>

      {/* Refine this report panel */}
      <div className="mt-16 mb-24 border-t border-rule pt-10" style={{ animation: "fadeUp 0.6s 0.4s cubic-bezier(0.2, 0.7, 0.2, 1) both" }}>
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] mb-4 gradient-text-subtle font-medium flex items-center gap-2">
          <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
            <path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Refine this report
        </div>
        <h3 className="text-[28px] font-normal tracking-[-0.025em] text-ink mb-2"
          style={{ fontFamily: "var(--font-display)" }}>
          Iterate until it&apos;s <em className="gradient-text" style={{ fontStyle: "italic", WebkitTextFillColor: "transparent" }}>perfect</em>
        </h3>
        <p className="text-[15px] text-muted font-light mb-6 max-w-[600px]" style={{ fontFamily: "var(--font-display)" }}>
          Tell the AI what to improve. You can refine as many times as you want.
        </p>

        <div className="bg-white border border-rule rounded-[14px] p-6 shadow-[0_1px_2px_rgba(20,19,42,0.04)]">
          {/* Feedback textarea */}
          <textarea
            className="w-full bg-paper border border-rule rounded-[8px] px-4 py-3 text-[15px] leading-[1.5] text-ink outline-none resize-none transition-all focus:border-purple focus:shadow-[0_0_0_3px_var(--color-purple-soft)] placeholder:text-muted-2 placeholder:italic min-h-[100px]"
            style={{ fontFamily: "var(--font-display)" }}
            rows={3}
            placeholder="e.g. &quot;Make the executive summary punchier&quot; or &quot;Finding #2 is weak, strengthen it&quot; or &quot;Use blue tones for Pfizer&quot;..."
            value={refineFeedback}
            onChange={e => setRefineFeedback(e.target.value)}
            disabled={refining}
          />

          {/* Quick-action buttons */}
          <div className="flex flex-wrap gap-2 mt-4">
            {[
              { label: "Sharpen findings", value: "Sharpen all findings — make the claims more specific and data-driven" },
              { label: "Add more evidence", value: "Add more supporting evidence and verbatim quotes to back up each finding" },
              { label: "Simplify language", value: "Simplify the language throughout — make it more accessible and less jargon-heavy" },
              { label: "Adjust tone", value: "Make the tone more confident and action-oriented" },
            ].map(action => (
              <button
                key={action.label}
                onClick={() => setRefineFeedback(prev => prev ? `${prev}\n${action.value}` : action.value)}
                disabled={refining}
                className="px-3 py-1.5 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.08em] font-medium bg-paper-2 text-ink-3 border border-rule hover:border-purple-rule hover:text-purple hover:bg-purple-soft transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {action.label}
              </button>
            ))}
          </div>

          {/* Design theme dropdown + Apply button */}
          <div className="flex items-center gap-4 mt-5 pt-5 border-t border-rule">
            <div className="flex items-center gap-2">
              <label className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted font-medium">Design</label>
              <select
                value={refineDesignTheme}
                onChange={e => setRefineDesignTheme(e.target.value)}
                disabled={refining}
                className="px-3 py-2 text-[13px] border border-rule rounded-[7px] bg-paper focus:border-purple focus:bg-white focus:shadow-[0_0_0_3px_var(--color-purple-soft)] outline-none transition-all"
              >
                <option value="default">Default</option>
                <option value="corporate_blue">Corporate Blue</option>
                <option value="pharma_green">Pharma Green</option>
                <option value="bold_pink">Bold Pink</option>
              </select>
            </div>

            <div className="flex-1" />

            {refining && (
              <div className="flex items-center gap-2 font-mono text-[11px] text-purple">
                <div className="w-4 h-4 border-2 border-purple border-t-transparent rounded-full animate-spin" />
                Refining...
              </div>
            )}

            <button
              onClick={handleRefine}
              disabled={refining || !refineFeedback.trim()}
              className="btn-gradient disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-none"
            >
              <span>{refining ? "Refining..." : "Apply changes"}</span>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 6h8 M6 2l4 4-4 4"/></svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
