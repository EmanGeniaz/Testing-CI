"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { uploadFile, setContext, setSchema, runTagging, getReportTypes, getStatus, getResults, type ReportTypeInfo } from "../lib/api";

interface StudioViewProps {
  onSessionReady: (sid: string, filename: string, cols: string[], rowCount: number) => void;
  onViewReport: () => void;
  sessionId: string | null;
}

type Phase = "compose" | "configure" | "running" | "report";
type ComposeMode = "chat" | "form";

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
  const [phase, setPhase] = useState<Phase>("compose");
  const [composeMode, setComposeMode] = useState<ComposeMode>("chat");
  const [prompt, setPrompt] = useState("");

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

  const thinkingRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getReportTypes()
      .then(res => { setReportTypes(res.report_types); setReportType(res.default); })
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
      setPhase("configure");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, []);

  const handleRun = async () => {
    if (!sessionId || !primaryCol) return;
    setError("");
    setPhase("running");
    setSteps([]);
    setProgress(0);
    setAnalyzedRows(0);

    addStep("Uploading and parsing dataset", "ingest");

    try {
      await setContext({ session_id: sessionId, dataset_type: "Single brand", focus_brand: "", additional_context: prompt });
      addStep("Dataset context configured", "config");

      await setSchema({ session_id: sessionId, primary_text_column: primaryCol, visible_columns: columns, ai_columns: [primaryCol] });
      addStep(`Schema mapped — primary text: ${primaryCol}`, "schema");

      await runTagging({ session_id: sessionId, provider, report_type: reportType });
      addStep(`Tagging started — ${provider} / ${reportType}`, "agent");

      onSessionReady(sessionId, file?.name || "dataset", columns, rowCount);
      pollStatus(sessionId);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start");
      setPhase("compose");
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

  // Compose phase
  if (phase === "compose") {
    return (
      <div className="px-12 py-14 max-w-[1280px]" style={{ animation: "fadeUp 0.7s cubic-bezier(0.2, 0.7, 0.2, 1) both" }}>
        {/* Hero */}
        <header className="mb-11">
          <div className="font-mono text-[11px] uppercase tracking-[0.18em] mb-[22px] inline-flex items-center gap-[10px] gradient-text-subtle font-medium">
            <span className="w-5 h-[1px] bg-gradient-to-r from-purple to-pink inline-block" />
            Consumer Intelligence Studio
          </div>
          <h1 className="text-[68px] leading-[0.98] tracking-[-0.035em] font-normal text-ink mb-[18px] max-w-[820px]"
            style={{ fontFamily: "var(--font-display)" }}>
            What would you like<br/>to <em className="gradient-text" style={{ fontStyle: "italic", WebkitTextFillColor: "transparent" }}>understand</em>?
          </h1>
          <p className="text-[20px] leading-[1.5] text-muted font-light max-w-[640px] tracking-[-0.01em]"
            style={{ fontFamily: "var(--font-display)" }}>
            Describe a question in plain language, or upload a dataset directly. The agent does the research; you keep the judgment.
          </p>
        </header>

        {/* Mode tabs */}
        <div className="flex gap-0 mb-4">
          {[
            { id: "chat" as ComposeMode, num: "01", label: "Ask" },
            { id: "form" as ComposeMode, num: "02", label: "Upload & Tag" },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setComposeMode(tab.id)}
              className={`py-2.5 mr-8 font-mono text-[11px] uppercase tracking-[0.14em] relative transition-colors font-medium
                ${composeMode === tab.id ? "text-ink" : "text-muted-2 hover:text-ink-3"}`}
            >
              <span className={composeMode === tab.id ? "gradient-text-subtle" : "text-faint"}>{tab.num}</span>
              <span className="ml-2">{tab.label}</span>
              {composeMode === tab.id && (
                <span className="absolute bottom-[-2px] left-0 right-0 h-[2px] bg-gradient-to-r from-purple to-pink rounded" />
              )}
            </button>
          ))}
        </div>

        {/* Chat mode */}
        {composeMode === "chat" && (
          <div>
            <div className="relative bg-white border border-rule rounded-[14px] p-7 pb-5 transition-all shadow-[0_1px_2px_rgba(20,19,42,0.04)] gradient-border focus-within:border-purple-rule focus-within:shadow-[0_4px_24px_rgba(108,76,255,0.12)]">
              <textarea
                className="w-full bg-transparent border-none outline-none resize-none text-[26px] leading-[1.35] text-ink font-normal tracking-[-0.02em] min-h-[80px] placeholder:text-muted-2 placeholder:italic"
                style={{ fontFamily: "var(--font-display)" }}
                rows={2}
                placeholder="A brand health read on Liquid Death versus the non-alc spirits set over the last 60 days..."
                value={prompt}
                onChange={e => setPrompt(e.target.value)}
              />
              <div className="flex items-center justify-between mt-3.5 pt-3.5 border-t border-rule">
                <div className="flex items-center gap-[18px] font-mono text-[10px] uppercase tracking-[0.1em] text-muted-2">
                  <span className="flex items-center gap-1.5">
                    <span className="font-mono text-[10px] px-1.5 py-0.5 bg-paper-2 border border-rule rounded text-muted">⏎</span> Run
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="font-mono text-[10px] px-1.5 py-0.5 bg-paper-2 border border-rule rounded text-muted">⇧⏎</span> New line
                  </span>
                </div>
                <button className="btn-gradient" onClick={() => setComposeMode("form")}>
                  <span>Upload data</span>
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 6h8 M6 2l4 4-4 4"/></svg>
                </button>
              </div>
            </div>

            {/* Suggestions */}
            <div className="mt-[22px] flex flex-wrap gap-2.5">
              {[
                { kind: "Brand", text: "Liquid Death — health read" },
                { kind: "Category", text: "Plant-based meat — Q1 trends" },
                { kind: "Pharma", text: "HPP patient journey insights" },
                { kind: "Gen Z", text: "Nike vs Adidas brand perception" },
              ].map(s => (
                <button
                  key={s.text}
                  onClick={() => { setPrompt(s.text); setComposeMode("form"); }}
                  className="px-4 py-[9px] bg-white border border-rule rounded-3xl text-[12.5px] text-ink-2 cursor-pointer transition-all flex items-center gap-2 hover:border-purple-rule hover:bg-purple-soft hover:-translate-y-px hover:shadow-[0_4px_12px_rgba(108,76,255,0.1)]"
                >
                  <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-purple font-medium">{s.kind}</span>
                  {s.text}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Upload mode */}
        {composeMode === "form" && (
          <div className="bg-white border border-rule rounded-[14px] p-7 shadow-[0_1px_2px_rgba(20,19,42,0.04)]">
            {/* Drop zone */}
            <div
              onDragOver={e => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={e => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
              onClick={() => document.getElementById("studio-file-input")?.click()}
              className={`flex flex-col items-center justify-center gap-3 py-10 rounded-xl border-2 border-dashed cursor-pointer transition-all mb-6
                ${dragging ? "border-purple bg-purple-soft" : "border-rule-2 hover:border-purple-rule hover:bg-paper-2"}`}
            >
              <input id="studio-file-input" type="file" className="hidden" accept=".csv,.xlsx,.xls,.json,.docx"
                onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
              {uploading ? (
                <div className="w-8 h-8 border-2 border-purple border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg className="w-8 h-8 text-muted-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
              <div className="text-[13px] text-ink-3 mb-4 flex items-center gap-2">
                <span className="font-mono text-[10px] uppercase px-1.5 py-0.5 rounded bg-purple-soft text-purple font-bold">
                  {file.name.split(".").pop()?.toUpperCase()}
                </span>
                <span className="font-medium">{file.name}</span>
                <span className="text-muted-2">{rowCount} rows x {columns.length} cols</span>
              </div>
            )}

            {prompt && (
              <div className="mb-4 p-3 bg-paper-2 rounded-lg border border-rule">
                <div className="font-mono text-[9px] uppercase tracking-[0.14em] text-purple font-medium mb-1">Context from prompt</div>
                <p className="text-[13px] text-ink-2 italic" style={{ fontFamily: "var(--font-display)" }}>{prompt}</p>
              </div>
            )}

            {error && (
              <div className="text-[12px] text-pink bg-pink-soft border border-pink/20 px-3 py-2 rounded-lg mb-4">{error}</div>
            )}
          </div>
        )}
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
            <button onClick={() => setPhase("compose")} className="font-mono text-[11px] text-muted hover:text-ink transition-colors uppercase tracking-[0.1em]">
              ← Back
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
        <div className="grid gap-12" style={{ gridTemplateColumns: "1fr 320px" }}>
          {/* Main report */}
          <div className="min-w-0">
            <h1 className="text-[56px] leading-[1] tracking-[-0.035em] font-normal text-ink mb-4"
              style={{ fontFamily: "var(--font-display)" }}
              dangerouslySetInnerHTML={{ __html: report.title.replace(/\*([^*]+)\*/g, '<em class="gradient-text" style="font-style:italic;-webkit-text-fill-color:transparent">$1</em>') }} />

            <p className="text-[19px] leading-[1.5] text-muted font-light mb-7 max-w-[620px]"
              style={{ fontFamily: "var(--font-display)" }}>
              {report.subtitle}
            </p>

            {/* Metadata bar */}
            <div className="flex gap-7 py-4 border-t border-b border-rule mb-10 font-mono text-[11px] text-ink-3">
              {Object.entries(report.metadata).map(([key, val]) => (
                <div key={key} className="flex flex-col gap-1">
                  <span className="text-muted-2 text-[9px] uppercase tracking-[0.12em]">{key.replace(/_/g, " ")}</span>
                  <span className="text-ink text-[12px] font-medium">{val}</span>
                </div>
              ))}
            </div>

            {/* Sections */}
            {report.sections.map((sec, i) => (
              <div key={sec.id}>
                <h2 className="text-[28px] font-normal tracking-[-0.025em] text-ink mt-10 mb-[18px] flex items-baseline gap-3.5"
                  style={{ fontFamily: "var(--font-display)" }}>
                  <span className="font-mono text-[11px] text-purple font-medium tracking-[0.08em]">{String(i+1).padStart(2,"0")}</span>
                  {sec.heading}
                </h2>
                <p className="text-[17px] leading-[1.65] text-ink-2 mb-4 font-light max-w-[680px]"
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
              <div key={finding.number} className="grid gap-[22px] py-6 border-t border-rule" style={{ gridTemplateColumns: "100px 1fr" }}>
                <div className="flex flex-col gap-2">
                  <div className="text-[42px] leading-[1] font-normal tracking-[-0.03em] gradient-text"
                    style={{ fontFamily: "var(--font-display)", WebkitTextFillColor: "transparent" }}>
                    {String(finding.number).padStart(2,"0")}
                  </div>
                  <span className={`font-mono text-[9px] uppercase tracking-[0.12em] inline-flex items-center gap-[5px] w-max px-2 py-[3px] rounded font-medium
                    ${finding.confidence === "high" ? "text-green bg-green-soft" : "text-amber bg-amber-soft"}`}>
                    <span className={`w-[5px] h-[5px] rounded-full ${finding.confidence === "high" ? "bg-green" : "bg-amber"}`} />
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
            ))}

            {/* So what */}
            {report.so_what && (
              <>
                <h2 className="text-[28px] font-normal tracking-[-0.025em] text-ink mt-10 mb-[18px] flex items-baseline gap-3.5"
                  style={{ fontFamily: "var(--font-display)" }}>
                  <span className="font-mono text-[11px] text-purple font-medium tracking-[0.08em]">{String(report.sections.length + 2).padStart(2,"0")}</span>
                  So what
                </h2>
                <p className="text-[17px] leading-[1.65] text-ink-2 font-light max-w-[680px]"
                  style={{ fontFamily: "var(--font-display)" }}>
                  {report.so_what}
                </p>
              </>
            )}
          </div>

          {/* Evidence rail */}
          <aside className="sticky top-[90px] self-start border-l border-rule pl-6 max-h-[calc(100vh-130px)] overflow-y-auto">
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

          <div className="grid grid-cols-4 gap-4 mb-8">
            {[
              { label: "Total Rows", value: taggedData.length, color: "text-ink" },
              { label: "Positive", value: `${taggedData.length ? Math.round(taggedData.filter(r => r.sentiment === "Positive").length / taggedData.length * 100) : 0}%`, color: "text-green" },
              { label: "Negative", value: `${taggedData.length ? Math.round(taggedData.filter(r => r.sentiment === "Negative").length / taggedData.length * 100) : 0}%`, color: "text-pink" },
              { label: "Avg Confidence", value: `${taggedData.length ? Math.round(taggedData.reduce((a, r) => a + (Number(r.confidence) || 0), 0) / taggedData.length * 100) : 0}%`, color: "text-purple" },
            ].map(stat => (
              <div key={stat.label} className="bg-white border border-rule rounded-xl p-5 text-center">
                <div className={`text-[32px] font-normal tracking-[-0.03em] ${stat.color}`} style={{ fontFamily: "var(--font-display)" }}>
                  {stat.value}
                </div>
                <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted mt-1">{stat.label}</div>
              </div>
            ))}
          </div>

          <div className="flex gap-3">
            <button onClick={onViewReport} className="btn-gradient">
              <span>View in workbench</span>
            </button>
            <button onClick={() => setPhase("compose")} className="font-mono text-[11px] text-muted hover:text-ink uppercase tracking-[0.1em] px-5 py-2.5 border border-rule rounded-lg hover:border-purple-rule transition-all">
              New report
            </button>
          </div>
        </div>
      )}

      {/* Action bar */}
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-white/92 backdrop-blur-[20px] border border-rule rounded-xl px-[18px] py-3 flex items-center gap-4 z-50 shadow-[0_12px_40px_rgba(108,76,255,0.15),0_2px_8px_rgba(20,19,42,0.08)]"
        style={{ animation: "barIn 0.5s 0.3s cubic-bezier(0.2, 0.7, 0.2, 1) both" }}>
        <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted pr-4 border-r border-rule font-medium">
          <span className="text-green">●</span> {report ? "Draft ready · Awaiting review" : "Analysis complete"}
        </div>
        <button onClick={onViewReport} className="px-4 py-2 rounded-[6px] font-mono text-[11px] uppercase tracking-[0.1em] font-medium bg-transparent text-ink-3 border border-rule hover:text-ink hover:border-purple-rule hover:bg-purple-soft transition-all">
          View data
        </button>
        <button className="px-4 py-2 rounded-[6px] font-mono text-[11px] uppercase tracking-[0.1em] font-medium bg-gradient-to-r from-purple to-pink text-white shadow-[0_4px_12px_rgba(108,76,255,0.25)] hover:-translate-y-px hover:shadow-[0_6px_16px_rgba(108,76,255,0.35)] transition-all">
          Approve & export
        </button>
      </div>
    </div>
  );
}
