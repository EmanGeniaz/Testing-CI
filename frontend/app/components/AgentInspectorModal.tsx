"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import {
  uploadFile,
  setContext,
  setSchema,
  runTagging,
  getReportTypes,
  getStatus,
  getResults,
  getActiveMCPConnectors,
  searchConnectorToSession,
  type ReportTypeInfo,
} from "../lib/api";

/* ─────────────────────────────────────────────────────────────────────── */
/*  Types                                                                  */
/* ─────────────────────────────────────────────────────────────────────── */

export interface AgentOption {
  id: string;
  name: string;
  description: string;
  initials: string;
  gradient: string;
}

interface AgentInspectorModalProps {
  agent: AgentOption;
  /** Legacy modal close — no longer used inside the workspace itself.
   * Tab close is handled by the AgentTabBar in the parent. Kept optional
   * so callers can still pass it without errors. */
  onClose?: () => void;
  onSessionReady: (sid: string, filename: string, cols: string[], rowCount: number) => void;
  onViewReport: () => void;
  /**
   * Reports per-tab metadata back to the tab bar (filename + status).
   * Optional — when omitted (legacy modal use), no-op.
   */
  onMetaChange?: (meta: { filename?: string; rowCount?: number; status: "idle" | "running" | "review" | "complete" | "error" }) => void;
}

export type TabStatus = "idle" | "running" | "review" | "complete" | "error";

type RunStatus = "idle" | "running" | "complete" | "error";
type SubAgentStatus = "waiting" | "running" | "complete" | "review";

interface SubAgent {
  id: number;
  name: string;
  meta: string;
  status: SubAgentStatus;
  result?: Record<string, unknown> | string | null;
  tool?: string;
}

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const INITIAL_SUBAGENTS: SubAgent[] = [
  { id: 1, name: "Data Acquisition", meta: "waiting", status: "waiting" },
  { id: 2, name: "Data Sanitization", meta: "waiting", status: "waiting" },
  { id: 3, name: "Schema Detection", meta: "waiting", status: "waiting" },
  { id: 4, name: "Auto-Tagging", meta: "waiting", status: "waiting" },
  { id: 5, name: "Tag Validation", meta: "waiting", status: "waiting" },
  { id: 6, name: "Pattern Analysis", meta: "waiting", status: "waiting" },
  { id: 7, name: "Insight Generation", meta: "waiting", status: "waiting" },
  { id: 8, name: "Design & Styling", meta: "waiting", status: "waiting" },
  { id: 9, name: "Report Rendering", meta: "waiting", status: "waiting" },
];

const TOOL_TO_SUBAGENT: Record<string, number[]> = {
  analyze_data_quality: [1],
  clean_data: [2],
  select_skill: [3],
  create_custom_schema: [3],
  run_tagging: [4, 5],
  analyze_patterns: [6],
  self_review: [7],
  generate_report: [7, 8, 9],
};

/* ─────────────────────────────────────────────────────────────────────── */
/*  Component                                                              */
/* ─────────────────────────────────────────────────────────────────────── */

export default function AgentInspectorModal({
  agent,
  onSessionReady,
  onViewReport,
  onMetaChange,
}: AgentInspectorModalProps) {
  /* run state */
  const [mode, setMode] = useState<"auto" | "inspect">("inspect");
  const [runStatus, setRunStatus] = useState<RunStatus>("idle");

  /* upload state */
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [columns, setColumns] = useState<string[]>([]);
  const [rowCount, setRowCount] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");

  /* config */
  const [contextBrief, setContextBrief] = useState("");
  const [primaryCol, setPrimaryCol] = useState("");
  const [provider, setProvider] = useState("claude");
  const [reportTypes, setReportTypes] = useState<ReportTypeInfo[]>([]);
  const [reportType, setReportType] = useState("");

  /* pipeline */
  const [subAgents, setSubAgents] = useState<SubAgent[]>(INITIAL_SUBAGENTS);
  const [selectedId, setSelectedId] = useState<number>(1);
  const [elapsed, setElapsed] = useState(0);
  const [progress, setProgress] = useState(0);
  const [analyzedRows, setAnalyzedRows] = useState(0);

  /* checkpoint (inspect mode) */
  const [checkpoint, setCheckpoint] = useState<{ tool: string; subAgentId: number } | null>(null);
  const [refineOpen, setRefineOpen] = useState(false);
  const [refineText, setRefineText] = useState("");
  const [continueBusy, setContinueBusy] = useState(false);

  const startTimeRef = useRef<number | null>(null);
  const elapsedTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /* report */
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [taggedData, setTaggedData] = useState<Record<string, unknown>[]>([]);

  /* memory-tagged thoughts streamed from the orchestrator */
  const [memoryThoughts, setMemoryThoughts] = useState<string[]>([]);

  /* ── effects ──────────────────────────────────────────────────────── */

  useEffect(() => {
    getReportTypes()
      .then(res => {
        setReportTypes(res.report_types);
        setReportType(res.default);
      })
      .catch(() => {});
  }, []);

  // No longer a modal — Escape no longer closes. Tab close is handled by the tab bar.

  useEffect(() => {
    return () => {
      if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current);
    };
  }, []);

  // Report tab metadata up to the parent tab bar.
  useEffect(() => {
    if (!onMetaChange) return;
    let status: TabStatus = "idle";
    if (runStatus === "error") status = "error";
    else if (runStatus === "complete") status = "complete";
    else if (checkpoint) status = "review";
    else if (runStatus === "running") status = "running";
    onMetaChange({
      filename: file?.name,
      rowCount,
      status,
    });
  }, [onMetaChange, runStatus, checkpoint, file, rowCount]);

  /* ── helpers ──────────────────────────────────────────────────────── */

  const updateSubAgent = useCallback(
    (id: number, patch: Partial<SubAgent>) => {
      setSubAgents(prev => prev.map(sa => (sa.id === id ? { ...sa, ...patch } : sa)));
    },
    []
  );

  const markToolRunning = useCallback((tool: string) => {
    const ids = TOOL_TO_SUBAGENT[tool];
    if (!ids) return;
    setSubAgents(prev =>
      prev.map(sa =>
        ids.includes(sa.id)
          ? { ...sa, status: "running", meta: "running…", tool }
          : sa
      )
    );
    setSelectedId(ids[0]);
  }, []);

  const markToolComplete = useCallback(
    (tool: string, result: Record<string, unknown> | string) => {
      const ids = TOOL_TO_SUBAGENT[tool];
      if (!ids) return;
      setSubAgents(prev =>
        prev.map(sa => {
          if (!ids.includes(sa.id)) return sa;
          let meta = "complete";
          if (tool === "analyze_data_quality" && typeof result === "object" && result) {
            const rowsField = (result as Record<string, unknown>).row_count ?? (result as Record<string, unknown>).rows;
            if (rowsField) meta = `${rowsField} rows`;
          } else if (tool === "clean_data" && typeof result === "object" && result) {
            const cleaned = (result as Record<string, unknown>).cleaned_rows ?? (result as Record<string, unknown>).remaining;
            const dups = (result as Record<string, unknown>).duplicates_removed ?? (result as Record<string, unknown>).removed;
            if (cleaned) meta = `${cleaned} rows · ${dups ?? 0} removed`;
          } else if (tool === "run_tagging" && typeof result === "object" && result) {
            const tagged = (result as Record<string, unknown>).tagged_rows ?? (result as Record<string, unknown>).rows;
            if (tagged) meta = `${tagged} rows tagged`;
          }
          return { ...sa, status: "complete", meta, result };
        })
      );
    },
    []
  );

  /* ── checkpoint actions (inspect mode) ───────────────────────────── */

  const sendContinue = useCallback(
    async (action: "approve" | "refine", feedback?: string) => {
      if (!sessionId || !checkpoint) return;
      setContinueBusy(true);
      try {
        const res = await fetch(`${BASE}/orchestrate/${sessionId}/continue`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action, feedback }),
        });
        if (!res.ok) throw new Error(`continue failed (${res.status})`);

        // Optimistically advance the UI back to "running" for the checkpointed step.
        const ids = TOOL_TO_SUBAGENT[checkpoint.tool] || [];
        if (action === "approve") {
          setSubAgents(prev =>
            prev.map(sa =>
              ids.includes(sa.id) && sa.status === "review"
                ? { ...sa, status: "complete", meta: "approved" }
                : sa
            )
          );
        } else {
          setSubAgents(prev =>
            prev.map(sa =>
              ids.includes(sa.id)
                ? { ...sa, status: "running", meta: "refining…" }
                : sa
            )
          );
        }
        setCheckpoint(null);
        setRefineOpen(false);
        setRefineText("");
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Continue failed");
      } finally {
        setContinueBusy(false);
      }
    },
    [sessionId, checkpoint]
  );

  /* ── upload ───────────────────────────────────────────────────────── */

  /** Banner shown after a successful connector pull. */
  const [connectorPullBanner, setConnectorPullBanner] = useState<string>("");

  const handleConnectorPull = useCallback(
    async (
      connectorId: string,
      connectorName: string,
      query: string,
      limit: number,
      filters: Record<string, unknown>,
    ) => {
      setError("");
      setUploading(true);
      try {
        const res = await searchConnectorToSession(connectorId, query, limit, filters);
        // Create a virtual File so the existing "uploaded" UI lights up.
        const virtualFile = new File([""], res.filename, { type: "application/json" });
        setFile(virtualFile);
        setColumns(res.columns);
        setRowCount(res.row_count);
        setSessionId(res.session_id);
        setPrimaryCol("text"); // standardized connector schema
        setConnectorPullBanner(
          `✓ Pulled ${res.row_count} rows from ${connectorName} · query: ${query}`
        );
        updateSubAgent(1, {
          status: "complete",
          meta: `${res.row_count} rows · ${connectorName}`,
        });
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Connector pull failed");
      } finally {
        setUploading(false);
      }
    },
    [updateSubAgent]
  );

  const handleFile = useCallback(async (f: File) => {
    setFile(f);
    setError("");
    setUploading(true);
    setConnectorPullBanner("");
    try {
      const res = await uploadFile(f);
      setColumns(res.columns);
      setRowCount(res.row_count);
      setSessionId(res.session_id);
      const defaultPrimary =
        res.columns.find((c: string) =>
          /detail|text|content|body|description|review/i.test(c)
        ) || res.columns[0];
      setPrimaryCol(defaultPrimary);
      // sub-agent 1 acquired
      updateSubAgent(1, { status: "complete", meta: `${res.row_count} rows · uploaded` });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, [updateSubAgent]);

  /* ── run orchestrator ─────────────────────────────────────────────── */

  const handleRun = async () => {
    if (!sessionId || !primaryCol) return;
    setError("");
    setRunStatus("running");
    setReport(null);
    setProgress(0);
    setAnalyzedRows(0);
    setMemoryThoughts([]);

    // start elapsed timer
    startTimeRef.current = Date.now();
    if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current);
    elapsedTimerRef.current = setInterval(() => {
      if (startTimeRef.current) {
        setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }
    }, 1000);

    onSessionReady(sessionId, file?.name || "dataset", columns, rowCount);

    const userPrompt = [
      contextBrief,
      `Use the ${agent.name} skill.`,
    ].filter(Boolean).join("\n\n");

    try {
      const res = await fetch(`${BASE}/orchestrate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          prompt: userPrompt,
          provider,
          inspect_mode: mode === "inspect",
        }),
      });

      if (!res.ok || !res.body) throw new Error("Orchestrator unavailable");

      // side-channel polling for granular progress
      let pollActive = true;
      (async () => {
        while (pollActive) {
          await new Promise(r => setTimeout(r, 4000));
          if (!pollActive) break;
          try {
            const st = await getStatus(sessionId);
            if (st.progress > 0) setProgress(st.progress);
            if (st.analyzed_rows > 0) setAnalyzedRows(st.analyzed_rows);
          } catch {}
        }
      })();

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) { pollActive = false; break; }
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const ev = JSON.parse(line);
            if (ev.type === "thinking" && ev.meta === "memory" && typeof ev.text === "string") {
              setMemoryThoughts(prev => [...prev, ev.text]);
            } else if (ev.type === "tool_call" && typeof ev.tool === "string") {
              markToolRunning(ev.tool);
            } else if (ev.type === "tool_result" && typeof ev.tool === "string") {
              markToolComplete(ev.tool, ev.result);
              // Capture the report when generate_report finishes so the
              // Insights panel can render findings even if the orchestrator
              // doesn't emit a separate "complete" event.
              if (ev.tool === "generate_report" && ev.result?.report) {
                setReport(ev.result.report);
                // generate_report is effectively the end of the pipeline.
                // Mark remaining sub-agents complete and the run as done.
                setSubAgents(prev => prev.map(sa =>
                  sa.status === "waiting" || sa.status === "running"
                    ? { ...sa, status: "complete", meta: "complete" }
                    : sa
                ));
                setRunStatus(s => (s === "running" ? "complete" : s));
              }
            } else if (ev.type === "checkpoint" && typeof ev.tool === "string") {
              const ids = TOOL_TO_SUBAGENT[ev.tool] || [];
              if (ids.length > 0) {
                setCheckpoint({ tool: ev.tool, subAgentId: ids[0] });
                setRefineOpen(false);
                setRefineText("");
                setSubAgents(prev =>
                  prev.map(sa =>
                    ids.includes(sa.id)
                      ? { ...sa, status: "review", meta: "needs approval", tool: ev.tool }
                      : sa
                  )
                );
                setSelectedId(ids[0]);
              }
            } else if (ev.type === "progress") {
              setProgress(ev.progress ?? 0);
              setAnalyzedRows(ev.analyzed_rows ?? 0);
            } else if (ev.type === "complete") {
              if (ev.report) setReport(ev.report);
              // ensure remaining are complete
              setSubAgents(prev => prev.map(sa =>
                sa.status === "waiting" || sa.status === "running"
                  ? { ...sa, status: "complete", meta: "complete" }
                  : sa
              ));
              try {
                const results = await getResults(sessionId);
                setTaggedData(results.analyzed_data ?? []);
              } catch {}
              setRunStatus("complete");
              setSelectedId(9);
            } else if (ev.type === "error") {
              setRunStatus("error");
              setError(ev.message || ev.text || "Agent error");
            }
          } catch {
            // skip malformed lines
          }
        }
      }
      if (runStatus !== "error") setRunStatus(s => (s === "running" ? "complete" : s));
    } catch {
      // fallback to direct pipeline
      try {
        await setContext({
          session_id: sessionId,
          dataset_type: "Single brand",
          focus_brand: "",
          additional_context: contextBrief,
        });
        await setSchema({
          session_id: sessionId,
          primary_text_column: primaryCol,
          visible_columns: columns,
          ai_columns: [primaryCol],
        });
        const backendIds = reportTypes.map(rt => rt.id);
        const eff = backendIds.includes(agent.id) ? agent.id : reportType;
        await runTagging({ session_id: sessionId, provider, report_type: eff });
        markToolRunning("run_tagging");
        pollFallback(sessionId);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to start");
        setRunStatus("error");
      }
    } finally {
      if (elapsedTimerRef.current) {
        clearInterval(elapsedTimerRef.current);
        elapsedTimerRef.current = null;
      }
    }
  };

  const pollFallback = useCallback(
    async (sid: string) => {
      const poll = async () => {
        try {
          const st = await getStatus(sid);
          setProgress(st.progress ?? 0);
          setAnalyzedRows(st.analyzed_rows ?? 0);
          if (st.status === "complete") {
            markToolComplete("run_tagging", { tagged_rows: st.analyzed_rows });
            const res = await getResults(sid);
            setTaggedData(res.analyzed_data ?? []);
            try {
              const reportRes = await fetch(`${BASE}/session/${sid}/generate-report`, { method: "POST" });
              if (reportRes.ok) {
                const reportData = await reportRes.json();
                setReport(reportData);
                markToolComplete("generate_report", reportData);
              }
            } catch {}
            setSubAgents(prev => prev.map(sa =>
              sa.status === "waiting" || sa.status === "running"
                ? { ...sa, status: "complete", meta: "complete" }
                : sa
            ));
            setRunStatus("complete");
            setSelectedId(9);
            return;
          }
          if (st.status === "error") {
            setError(st.error_message || "Tagging failed");
            setRunStatus("error");
            return;
          }
          setTimeout(poll, 3000);
        } catch {
          setTimeout(poll, 5000);
        }
      };
      poll();
    },
    [markToolComplete]
  );

  /* ── derived ──────────────────────────────────────────────────────── */

  const selected = useMemo(
    () => subAgents.find(sa => sa.id === selectedId) ?? subAgents[0],
    [subAgents, selectedId]
  );

  const elapsedLabel = useMemo(() => {
    if (!elapsed) return runStatus === "idle" ? "—" : "0s";
    const m = Math.floor(elapsed / 60);
    const s = elapsed % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
  }, [elapsed, runStatus]);

  const currentStep = useMemo(() => {
    const running = subAgents.find(sa => sa.status === "running");
    if (running) return `${String(running.id).padStart(2, "0")} of 09 · ${running.name}`;
    if (runStatus === "complete") return "09 of 09 · Complete";
    if (runStatus === "idle" && !sessionId) return "00 of 09 · Awaiting data";
    if (runStatus === "idle") return "00 of 09 · Ready to run";
    return "—";
  }, [subAgents, runStatus, sessionId]);

  const statusLabel = useMemo(() => {
    if (runStatus === "error") return { text: "● Error", color: "var(--color-pink)" };
    if (runStatus === "complete") return { text: "● Complete", color: "var(--color-green)" };
    if (checkpoint) return { text: "⏸ Waiting for approval", color: "var(--color-amber)" };
    if (runStatus === "running") return { text: "● Running", color: "var(--color-purple)" };
    if (sessionId) return { text: "● Ready", color: "var(--color-amber)" };
    return { text: "● Awaiting data", color: "var(--color-muted)" };
  }, [runStatus, sessionId, checkpoint]);

  /* ── render ───────────────────────────────────────────────────────── */

  return (
    <div className="px-6 pb-6 pt-4">
      <div
        className="grid w-full overflow-hidden"
        style={{
          background: "var(--color-paper)",
          borderRadius: 14,
          border: "1px solid var(--color-rule)",
          height: "calc(100vh - 130px)",
          gridTemplateRows: "auto auto 1fr",
        }}
      >
        {/* HEADER */}
        <div className="flex items-center gap-4 bg-white border-b border-rule px-6 py-[18px]">
          <div
            className="w-11 h-11 rounded-[12px] flex items-center justify-center text-white font-mono text-[14px] font-bold flex-shrink-0"
            style={{ background: agent.gradient }}
          >
            {agent.initials}
          </div>
          <div className="flex-1 min-w-0">
            <div
              className="text-[22px] font-medium leading-none mb-1 tracking-[-0.02em] text-ink"
              style={{ fontFamily: "var(--font-display)" }}
            >
              {agent.name} Agent
            </div>
            <div className="font-mono text-[11px] uppercase tracking-[0.1em] text-muted">
              {agent.description.toLowerCase()} · 9 sub-agents
            </div>
          </div>

          {/* Mode toggle */}
          <div
            className="flex gap-[2px] p-[3px] rounded-[8px] border border-rule"
            style={{ background: "var(--color-paper-2)" }}
          >
            {(["auto", "inspect"] as const).map(m => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-[14px] py-[6px] rounded-[6px] font-mono text-[10px] uppercase tracking-[0.1em] font-medium transition-all ${
                  mode === m ? "bg-white text-purple shadow-[0_1px_3px_rgba(108,76,255,0.1)]" : "text-muted"
                }`}
              >
                {m}
              </button>
            ))}
          </div>

        </div>

        {/* INFO BAR */}
        <div className="bg-white border-b border-rule px-6 py-3 flex gap-7 items-center">
          <InfoItem label="Dataset" value={file && rowCount > 0 ? `${file.name} · ${rowCount} rows` : "—"} />
          <InfoItem label="Skill" value={agent.name} />
          <InfoItem
            label="Step"
            value={currentStep}
            valueStyle={{ color: runStatus === "running" ? "var(--color-purple)" : undefined }}
          />
          <InfoItem label="Elapsed" value={elapsedLabel} />
          <div className="ml-auto">
            <InfoItem label="Status" value={statusLabel.text} valueStyle={{ color: statusLabel.color }} />
          </div>
        </div>

        {/* MEMORY RIBBON — shown when the orchestrator invokes past patterns */}
        {memoryThoughts.length > 0 && (
          <div
            className="border-b border-rule px-6 py-2.5 flex items-start gap-3"
            style={{ background: "var(--color-purple-soft)" }}
          >
            <span
              className="font-mono text-[9px] uppercase tracking-[0.12em] font-semibold px-1.5 py-0.5 rounded flex-shrink-0 mt-0.5"
              style={{ background: "var(--color-purple)", color: "white" }}
              title="The agent is applying patterns learned from your past runs"
            >
              Memory
            </span>
            <div className="flex-1 min-w-0">
              <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted-2 mb-0.5">
                Applying {memoryThoughts.length} past-run pattern{memoryThoughts.length === 1 ? "" : "s"}
              </div>
              <div className="text-[12.5px] leading-[1.5] text-ink-2 line-clamp-2">
                {memoryThoughts[memoryThoughts.length - 1]}
              </div>
            </div>
          </div>
        )}

        {/* BODY */}
        <div className="grid overflow-hidden min-h-0" style={{ gridTemplateColumns: "320px 1fr" }}>
          {/* PIPELINE LEFT */}
          <div className="bg-white border-r border-rule p-[18px] overflow-y-auto">
            <h3 className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-2 mb-3 font-semibold">
              Pipeline · 9 sub-agents
            </h3>
            <div className="flex flex-col gap-1">
              {subAgents.map(sa => (
                <PipelineRow
                  key={sa.id}
                  sub={sa}
                  selected={sa.id === selectedId}
                  onClick={() => setSelectedId(sa.id)}
                />
              ))}
            </div>
          </div>

          {/* DETAILS RIGHT */}
          <div className="overflow-y-auto p-6" style={{ background: "var(--color-paper)" }}>
            {/* Show combined data + configure pane until run starts */}
            {runStatus === "idle" ? (
              <DataPane
                dragging={dragging}
                uploading={uploading}
                error={error}
                file={file}
                rowCount={rowCount}
                columns={columns}
                sessionId={sessionId}
                contextBrief={contextBrief}
                setContextBrief={setContextBrief}
                primaryCol={primaryCol}
                setPrimaryCol={setPrimaryCol}
                provider={provider}
                setProvider={setProvider}
                onRun={handleRun}
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  const f = e.dataTransfer.files[0];
                  if (f) handleFile(f);
                }}
                onFile={handleFile}
                onConnectorPull={handleConnectorPull}
                connectorPullBanner={connectorPullBanner}
              />
            ) : (
              <SubAgentDetail
                sub={selected}
                runStatus={runStatus}
                progress={progress}
                analyzedRows={analyzedRows}
                rowCount={rowCount}
                taggedData={taggedData}
                report={report}
                sessionId={sessionId || ""}
                onViewReport={onViewReport}
                checkpoint={checkpoint}
                refineOpen={refineOpen}
                refineText={refineText}
                setRefineOpen={setRefineOpen}
                setRefineText={setRefineText}
                continueBusy={continueBusy}
                onApprove={() => sendContinue("approve")}
                onRefineSubmit={() => {
                  const fb = refineText.trim();
                  if (!fb) return;
                  sendContinue("refine", fb);
                }}
              />
            )}
          </div>
        </div>
      </div>

    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────── */
/*  Sub-components                                                         */
/* ─────────────────────────────────────────────────────────────────────── */

function InfoItem({
  label,
  value,
  valueStyle,
}: {
  label: string;
  value: string;
  valueStyle?: React.CSSProperties;
}) {
  return (
    <div className="flex flex-col gap-[2px]">
      <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-2">{label}</span>
      <span className="text-[12px] font-medium text-ink" style={valueStyle}>
        {value}
      </span>
    </div>
  );
}

function PipelineRow({
  sub,
  selected,
  onClick,
}: {
  sub: SubAgent;
  selected: boolean;
  onClick: () => void;
}) {
  const numStyles: Record<SubAgentStatus, string> = {
    complete: "bg-green-soft text-green",
    running: "text-white",
    review: "bg-amber-soft text-amber",
    waiting: "text-muted-2",
  };
  const numBg: Record<SubAgentStatus, React.CSSProperties> = {
    complete: {},
    running: { background: "linear-gradient(135deg, var(--color-purple), var(--color-pink))" },
    review: {},
    waiting: { background: "var(--color-paper-2)" },
  };
  const iconStyles: Record<SubAgentStatus, { bg: string; char: string }> = {
    complete: { bg: "var(--color-green)", char: "✓" },
    running: { bg: "var(--color-purple)", char: "●" },
    review: { bg: "var(--color-amber)", char: "!" },
    waiting: { bg: "var(--color-faint)", char: "⋯" },
  };

  return (
    <button
      onClick={onClick}
      className={`grid gap-[10px] items-center text-left rounded-[8px] px-[11px] py-[9px] border transition-all cursor-pointer ${
        selected ? "border-purple-rule" : "border-transparent hover:bg-paper-2"
      }`}
      style={{
        gridTemplateColumns: "26px 1fr 16px",
        background: selected ? "var(--color-purple-soft)" : undefined,
      }}
    >
      <span
        className={`w-[26px] h-[26px] rounded-[6px] font-mono text-[10px] font-semibold flex items-center justify-center ${numStyles[sub.status]}`}
        style={numBg[sub.status]}
      >
        {String(sub.id).padStart(2, "0")}
      </span>
      <span className="min-w-0">
        <span className="block text-[13px] font-medium text-ink">{sub.name}</span>
        <span className="block font-mono text-[10px] text-muted truncate">{sub.meta}</span>
      </span>
      <span
        className="w-[14px] h-[14px] rounded-full flex items-center justify-center text-[9px] font-bold text-white"
        style={{
          background: iconStyles[sub.status].bg,
          animation: sub.status === "running" ? "pulse 1.5s ease-in-out infinite" : undefined,
        }}
      >
        {iconStyles[sub.status].char}
      </span>
      <style jsx>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(0.85); }
        }
      `}</style>
    </button>
  );
}

/* ── Upload pane (no session yet) ──────────────────────────────────── */

function DataPane({
  dragging,
  uploading,
  error,
  file,
  rowCount,
  columns,
  sessionId,
  contextBrief,
  setContextBrief,
  primaryCol,
  setPrimaryCol,
  provider,
  setProvider,
  onRun,
  onDragOver,
  onDragLeave,
  onDrop,
  onFile,
  onConnectorPull,
  connectorPullBanner,
}: {
  dragging: boolean;
  uploading: boolean;
  error: string;
  file: File | null;
  rowCount: number;
  columns: string[];
  sessionId: string | null;
  contextBrief: string;
  setContextBrief: (v: string) => void;
  primaryCol: string;
  setPrimaryCol: (v: string) => void;
  provider: string;
  setProvider: (v: string) => void;
  onRun: () => void;
  onDragOver: (e: React.DragEvent) => void;
  onDragLeave: () => void;
  onDrop: (e: React.DragEvent) => void;
  onFile: (f: File) => void;
  onConnectorPull: (
    connectorId: string,
    connectorName: string,
    query: string,
    limit: number,
    filters: Record<string, unknown>,
  ) => void;
  connectorPullBanner: string;
}) {
  /* Active connectors → which cards unlock. */
  const [enabledConnectorIds, setEnabledConnectorIds] = useState<Set<string>>(new Set());
  const [pullFormFor, setPullFormFor] = useState<string | null>(null);

  useEffect(() => {
    getActiveMCPConnectors()
      .then(res => {
        setEnabledConnectorIds(new Set(res.connectors.map(c => c.id)));
      })
      .catch(() => {});
  }, []);
  const DATA_SOURCES: { category: string; sources: { id: string; name: string; icon: string; available: boolean }[] }[] = [
    {
      category: "Social Listening Platforms",
      sources: [
        { id: "brandwatch", name: "Brandwatch", icon: "📡", available: false },
        { id: "meltwater", name: "Meltwater", icon: "💧", available: false },
        { id: "sprinklr", name: "Sprinklr", icon: "💦", available: false },
        { id: "talkwalker", name: "Talkwalker", icon: "👁", available: false },
      ],
    },
    {
      category: "Social Media Direct",
      sources: [
        { id: "reddit", name: "Reddit API", icon: "🤖", available: false },
        { id: "twitter", name: "X / Twitter API", icon: "𝕏", available: false },
        { id: "meta", name: "Meta API", icon: "📘", available: false },
      ],
    },
    {
      category: "InfoVision API",
      sources: [
        { id: "infovision", name: "InfoVision API", icon: "🔮", available: false },
      ],
    },
    {
      category: "Traditional Media",
      sources: [
        { id: "news_api", name: "News API", icon: "📰", available: false },
        { id: "print", name: "Print Archives", icon: "📚", available: false },
      ],
    },
  ];

  return (
    <div>
      <div className="flex items-center gap-[14px] mb-4 pb-4 border-b border-rule">
        <div
          className="w-[38px] h-[38px] rounded-[10px] text-white font-mono text-[13px] font-semibold flex items-center justify-center"
          style={{ background: "linear-gradient(135deg, var(--color-purple), var(--color-pink))" }}
        >
          01
        </div>
        <div className="flex-1">
          <div className="text-[20px] font-medium tracking-[-0.02em] leading-none mb-[3px] text-ink"
            style={{ fontFamily: "var(--font-display)" }}>
            Data sources
          </div>
          <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted">
            Upload a file or connect a source · multi-source coming soon
          </div>
        </div>
      </div>

      {/* File Upload — compact when file is loaded */}
      <div className="bg-white border border-rule rounded-[12px] p-5 mb-4">
        <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-2 mb-2.5 font-semibold flex items-center justify-between">
          <span>Upload File</span>
          {sessionId && file && (
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] px-2.5 py-1 rounded-xl font-medium" style={{ background: "var(--color-green-soft)", color: "var(--color-green)" }}>
              ✓ Uploaded
            </span>
          )}
        </div>
        {sessionId && file ? (
          <div className="flex items-center gap-3 p-3 bg-paper border border-rule rounded-[8px]">
            <div className="w-9 h-9 rounded-[8px] bg-purple-soft text-purple flex items-center justify-center font-mono text-[10px] font-bold uppercase">
              {file.name.split(".").pop() || "FILE"}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[13px] font-medium text-ink truncate">{file.name}</div>
              <div className="font-mono text-[10px] text-muted mt-0.5">{rowCount} rows · {columns.length} cols</div>
            </div>
            <button
              onClick={() => document.getElementById("modal-file-input")?.click()}
              className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted hover:text-purple transition-colors px-2.5 py-1.5 border border-rule rounded-[6px] hover:border-purple-rule"
            >
              Replace
            </button>
            <input
              id="modal-file-input"
              type="file"
              className="hidden"
              accept=".csv,.xlsx,.xls,.json,.docx"
              onChange={e => {
                const f = e.target.files?.[0];
                if (f) onFile(f);
              }}
            />
          </div>
        ) : (
          <div
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            onClick={() => document.getElementById("modal-file-input")?.click()}
            className={`flex flex-col items-center justify-center gap-3 py-8 rounded-xl border-2 border-dashed cursor-pointer transition-all ${
              dragging ? "border-purple bg-purple-soft" : "border-rule-2 hover:border-purple-rule hover:bg-paper-2"
            }`}
          >
            <input
              id="modal-file-input"
              type="file"
              className="hidden"
              accept=".csv,.xlsx,.xls,.json,.docx"
              onChange={e => {
                const f = e.target.files?.[0];
                if (f) onFile(f);
              }}
            />
            {uploading ? (
              <div className="w-7 h-7 border-2 border-purple border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg className="w-7 h-7 text-muted-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
              </svg>
            )}
            <p className="text-[13px] text-ink-3">
              {uploading ? "Uploading…" : "Drop a file here or click to browse"}
            </p>
            <div className="flex gap-1.5">
              {["xlsx", "csv", "json", "docx"].map(f => (
                <span key={f}
                  className="font-mono text-[10px] uppercase px-2 py-0.5 bg-paper-2 rounded text-muted tracking-wide">
                  {f}
                </span>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="mt-3 text-[12px] text-pink bg-pink-soft border border-pink/20 px-3 py-2 rounded-lg">
            {error}
          </div>
        )}
      </div>

      {/* Connector pull success banner */}
      {connectorPullBanner && (
        <div
          className="mb-4 px-3 py-2.5 text-[12px] rounded-lg border"
          style={{
            background: "var(--color-green-soft)",
            color: "var(--color-green)",
            borderColor: "var(--color-green)",
          }}
        >
          {connectorPullBanner}
        </div>
      )}

      {/* Connector Sources */}
      {DATA_SOURCES.map(group => (
        <div key={group.category} className="bg-white border border-rule rounded-[12px] p-4 mb-3">
          <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-2 mb-2.5 font-semibold">
            {group.category}
          </div>
          <div className="grid grid-cols-2 gap-2">
            {group.sources.map(src => {
              const unlocked = enabledConnectorIds.has(src.id);
              const formOpen = pullFormFor === src.id;
              return (
                <div key={src.id} className={formOpen ? "col-span-2" : ""}>
                  <button
                    type="button"
                    onClick={() => {
                      if (!unlocked) return;
                      setPullFormFor(formOpen ? null : src.id);
                    }}
                    disabled={!unlocked}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 border rounded-[8px] transition-all ${
                      unlocked
                        ? "border-purple-rule bg-purple-soft/40 hover:bg-purple-soft cursor-pointer"
                        : "border-rule bg-paper/50 cursor-not-allowed opacity-70"
                    }`}
                    title={unlocked ? "Pull data via this connector" : "Coming soon — configure in MCP panel"}
                  >
                    <span className="text-[15px]">{src.icon}</span>
                    <span className={`text-[12px] flex-1 text-left ${unlocked ? "text-ink" : "text-ink-3"}`}>
                      {src.name}
                    </span>
                    {unlocked ? (
                      <span
                        className="font-mono text-[9px] uppercase tracking-[0.1em] px-1.5 py-0.5 rounded font-semibold"
                        style={{ background: "var(--color-green-soft)", color: "var(--color-green)" }}
                      >
                        Live
                      </span>
                    ) : (
                      <svg width="11" height="11" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted-2">
                        <rect x="3" y="6" width="8" height="6" rx="1"/><path d="M5 6V4a2 2 0 014 0v2"/>
                      </svg>
                    )}
                  </button>
                  {formOpen && unlocked && (
                    <ConnectorPullForm
                      connectorId={src.id}
                      connectorName={src.name}
                      busy={uploading}
                      onCancel={() => setPullFormFor(null)}
                      onSubmit={(query, limit, filters) =>
                        onConnectorPull(src.id, src.name, query, limit, filters)
                      }
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {/* Context Brief — always visible, persists */}
      <div className="bg-white border border-rule rounded-[12px] p-4 mt-4">
        <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-2 mb-2 font-semibold">
          Context Brief (optional)
        </div>
        <textarea
          className="w-full bg-transparent border border-rule rounded-[8px] px-3 py-2.5 text-[14px] leading-[1.5] text-ink outline-none resize-none transition-all focus:border-purple focus:shadow-[0_0_0_3px_var(--color-purple-soft)] placeholder:text-muted-2 placeholder:italic min-h-[80px]"
          style={{ fontFamily: "var(--font-display)" }}
          rows={3}
          placeholder="Tell the agent what you're looking for…"
          value={contextBrief}
          onChange={e => setContextBrief(e.target.value)}
        />
        <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted-2 mt-1.5">
          Persists across upload · configure · run
        </div>
      </div>

      {/* Configure section — appears after upload */}
      {sessionId && columns.length > 0 && (
        <>
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-2 mt-6 mb-3 font-semibold flex items-center gap-2">
            <span>▾</span>
            <span>Configure & Run</span>
          </div>

          <div className="bg-white border border-rule rounded-[12px] p-5 space-y-5">
            <div>
              <label className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted font-medium block mb-2">
                Primary text column
              </label>
              <select
                value={primaryCol}
                onChange={e => setPrimaryCol(e.target.value)}
                className="w-full px-3 py-2.5 text-[14px] border border-rule rounded-[7px] bg-paper focus:border-purple focus:bg-white focus:shadow-[0_0_0_3px_var(--color-purple-soft)] outline-none transition-all"
              >
                {columns.map(col => (
                  <option key={col} value={col}>{col}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted font-medium block mb-2">
                AI provider
              </label>
              <select
                value={provider}
                onChange={e => setProvider(e.target.value)}
                className="w-full px-3 py-2.5 text-[14px] border border-rule rounded-[7px] bg-paper focus:border-purple focus:bg-white focus:shadow-[0_0_0_3px_var(--color-purple-soft)] outline-none transition-all"
              >
                {[
                  { id: "claude", label: "Claude (Anthropic)" },
                  { id: "gemini", label: "Gemini (Google)" },
                  { id: "openai", label: "OpenAI" },
                  { id: "groq", label: "Groq" },
                ].map(p => (
                  <option key={p.id} value={p.id}>{p.label}</option>
                ))}
              </select>
            </div>

            <div className="pt-2 border-t border-rule flex items-center justify-between">
              <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-2">
                {rowCount} rows ready
              </div>
              <button
                onClick={onRun}
                className="inline-flex items-center gap-2.5 px-5 py-2.5 rounded-[8px] text-white font-mono text-[11px] uppercase tracking-[0.12em] font-medium"
                style={{
                  background: "linear-gradient(135deg, var(--color-purple), var(--color-pink))",
                  boxShadow: "0 4px 12px rgba(108,76,255,0.25)",
                }}
              >
                <span>Run agent</span>
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M2 6h8 M6 2l4 4-4 4" />
                </svg>
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/* ── Connector pull form (inline, expands inside DataPane) ──────────── */

function ConnectorPullForm({
  connectorId,
  connectorName,
  busy,
  onSubmit,
  onCancel,
}: {
  connectorId: string;
  connectorName: string;
  busy: boolean;
  onSubmit: (query: string, limit: number, filters: Record<string, unknown>) => void;
  onCancel: () => void;
}) {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(100);
  const [dateFrom, setDateFrom] = useState("");
  const [subreddit, setSubreddit] = useState("all");

  const isReddit = connectorId === "reddit";
  const isNews = connectorId === "news_api";

  const submit = () => {
    const q = query.trim();
    if (!q) return;
    const filters: Record<string, unknown> = {};
    if (isReddit) {
      if (subreddit) filters.subreddit = subreddit;
    }
    if (isNews && dateFrom) {
      filters.from_date = dateFrom;
    }
    onSubmit(q, limit, filters);
  };

  return (
    <div className="mt-2 p-3 border border-purple-rule rounded-[8px] bg-white space-y-3">
      <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-2 font-semibold">
        Pull from {connectorName}
      </div>

      <div>
        <label className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted block mb-1">
          Query
        </label>
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="e.g. HPP patient experience"
          className="w-full px-2.5 py-1.5 text-[12px] border border-rule rounded-[6px] bg-paper focus:border-purple focus:bg-white focus:shadow-[0_0_0_3px_var(--color-purple-soft)] outline-none"
        />
      </div>

      <div>
        <label className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted block mb-1">
          Rows: {limit}
        </label>
        <input
          type="range"
          min={50}
          max={500}
          step={10}
          value={limit}
          onChange={e => setLimit(parseInt(e.target.value, 10))}
          className="w-full"
        />
      </div>

      {isReddit && (
        <div>
          <label className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted block mb-1">
            Subreddit
          </label>
          <input
            type="text"
            value={subreddit}
            onChange={e => setSubreddit(e.target.value)}
            placeholder="all"
            className="w-full px-2.5 py-1.5 text-[12px] border border-rule rounded-[6px] bg-paper focus:border-purple focus:bg-white outline-none"
          />
        </div>
      )}

      {isNews && (
        <div>
          <label className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted block mb-1">
            From date
          </label>
          <input
            type="date"
            value={dateFrom}
            onChange={e => setDateFrom(e.target.value)}
            className="w-full px-2.5 py-1.5 text-[12px] border border-rule rounded-[6px] bg-paper focus:border-purple focus:bg-white outline-none"
          />
        </div>
      )}

      <div className="flex items-center justify-end gap-2 pt-1">
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted hover:text-ink px-2.5 py-1.5 border border-rule rounded-[6px]"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={busy || !query.trim()}
          className="font-mono text-[10px] uppercase tracking-[0.12em] text-white px-3 py-1.5 rounded-[6px] disabled:opacity-50"
          style={{ background: "linear-gradient(135deg, var(--color-purple), var(--color-pink))" }}
        >
          {busy ? "Pulling…" : "Pull data"}
        </button>
      </div>
    </div>
  );
}

/* ── Configure pane (uploaded, not yet running) ────────────────────── */

function ConfigurePane({
  file,
  rowCount,
  columns,
  primaryCol,
  setPrimaryCol,
  provider,
  setProvider,
  contextBrief,
  setContextBrief,
  onRun,
  error,
}: {
  file: File | null;
  rowCount: number;
  columns: string[];
  primaryCol: string;
  setPrimaryCol: (v: string) => void;
  provider: string;
  setProvider: (v: string) => void;
  contextBrief: string;
  setContextBrief: (v: string) => void;
  onRun: () => void;
  error: string;
}) {
  return (
    <div>
      <div className="flex items-center gap-[14px] mb-4 pb-4 border-b border-rule">
        <div
          className="w-[38px] h-[38px] rounded-[10px] text-white font-mono text-[13px] font-semibold flex items-center justify-center"
          style={{ background: "linear-gradient(135deg, var(--color-purple), var(--color-pink))" }}
        >
          02
        </div>
        <div className="flex-1">
          <div
            className="text-[20px] font-medium tracking-[-0.02em] leading-none mb-[3px] text-ink"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Configure & run
          </div>
          <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted">
            {file?.name} · {rowCount} rows · {columns.length} cols
          </div>
        </div>
        <span
          className="font-mono text-[10px] uppercase tracking-[0.12em] px-3 py-[5px] rounded-xl font-medium"
          style={{ background: "var(--color-green-soft)", color: "var(--color-green)" }}
        >
          Ready
        </span>
      </div>

      <div className="bg-white border border-rule rounded-[12px] p-5 mb-4 space-y-5">
        <div>
          <label className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted font-medium block mb-2">
            Primary text column
          </label>
          <select
            value={primaryCol}
            onChange={e => setPrimaryCol(e.target.value)}
            className="w-full px-3 py-2.5 text-[14px] border border-rule rounded-[7px] bg-paper focus:border-purple focus:bg-white focus:shadow-[0_0_0_3px_var(--color-purple-soft)] outline-none transition-all"
          >
            {columns.map(col => (
              <option key={col} value={col}>
                {col}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted font-medium block mb-2">
            AI provider
          </label>
          <select
            value={provider}
            onChange={e => setProvider(e.target.value)}
            className="w-full px-3 py-2.5 text-[14px] border border-rule rounded-[7px] bg-paper focus:border-purple focus:bg-white focus:shadow-[0_0_0_3px_var(--color-purple-soft)] outline-none transition-all"
          >
            {[
              { id: "claude", label: "Claude (Anthropic)" },
              { id: "gemini", label: "Gemini (Google)" },
              { id: "openai", label: "OpenAI" },
              { id: "groq", label: "Groq" },
            ].map(p => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted font-medium block mb-2">
            Context Brief
          </label>
          <textarea
            value={contextBrief}
            onChange={e => setContextBrief(e.target.value)}
            rows={3}
            className="w-full px-3 py-2.5 text-[14px] border border-rule rounded-[7px] bg-paper focus:border-purple focus:bg-white focus:shadow-[0_0_0_3px_var(--color-purple-soft)] outline-none transition-all resize-none"
            style={{ fontFamily: "var(--font-display)" }}
            placeholder="What should the agent focus on?"
          />
          <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted-2 mt-1.5">
            Pre-filled from your earlier brief · edit any time
          </div>
        </div>

        {error && (
          <div className="text-[12px] text-pink bg-pink-soft border border-pink/20 px-3 py-2 rounded-lg">
            {error}
          </div>
        )}
      </div>

      <div className="flex justify-end pt-2">
        <button
          onClick={onRun}
          disabled={!primaryCol}
          className="px-5 py-[10px] rounded-[6px] font-mono text-[10px] uppercase tracking-[0.12em] font-medium text-white inline-flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          style={{
            background: "linear-gradient(135deg, var(--color-purple), var(--color-pink))",
            boxShadow: "0 3px 10px rgba(108,76,255,0.25)",
          }}
        >
          <span>Run agent</span>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M2 6h8 M6 2l4 4-4 4" />
          </svg>
        </button>
      </div>
    </div>
  );
}

/* ── Sub-agent detail panel ────────────────────────────────────────── */

function SubAgentDetail({
  sub,
  runStatus,
  progress,
  analyzedRows,
  rowCount,
  taggedData,
  report,
  sessionId,
  onViewReport,
  checkpoint,
  refineOpen,
  refineText,
  setRefineOpen,
  setRefineText,
  continueBusy,
  onApprove,
  onRefineSubmit,
}: {
  sub: SubAgent;
  runStatus: RunStatus;
  progress: number;
  analyzedRows: number;
  rowCount: number;
  taggedData: Record<string, unknown>[];
  report: Record<string, unknown> | null;
  sessionId: string;
  onViewReport: () => void;
  checkpoint: { tool: string; subAgentId: number } | null;
  refineOpen: boolean;
  refineText: string;
  setRefineOpen: (v: boolean) => void;
  setRefineText: (v: string) => void;
  continueBusy: boolean;
  onApprove: () => void;
  onRefineSubmit: () => void;
}) {
  const isCheckpointed = checkpoint?.subAgentId === sub.id;
  const statusBadge: Record<SubAgentStatus, { label: string; cls: string }> = {
    complete: { label: "Complete", cls: "bg-green-soft text-green" },
    running: { label: "Running", cls: "bg-purple-soft text-purple" },
    review: { label: "Needs approval", cls: "bg-amber-soft text-amber" },
    waiting: { label: "Waiting", cls: "bg-paper-2 text-muted" },
  };

  return (
    <div>
      <div className="flex items-center gap-[14px] mb-4 pb-4 border-b border-rule">
        <div
          className="w-[38px] h-[38px] rounded-[10px] text-white font-mono text-[13px] font-semibold flex items-center justify-center"
          style={{ background: "linear-gradient(135deg, var(--color-purple), var(--color-pink))" }}
        >
          {String(sub.id).padStart(2, "0")}
        </div>
        <div className="flex-1">
          <div
            className="text-[20px] font-medium tracking-[-0.02em] leading-none mb-[3px] text-ink"
            style={{ fontFamily: "var(--font-display)" }}
          >
            {sub.name}
          </div>
          <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted">{sub.meta}</div>
        </div>
        <span
          className={`font-mono text-[10px] uppercase tracking-[0.12em] px-3 py-[5px] rounded-xl font-medium ${statusBadge[sub.status].cls}`}
        >
          {statusBadge[sub.status].label}
        </span>
      </div>

      {/* per sub-agent content */}
      {sub.status === "waiting" && (
        <div className="text-[13px] text-muted leading-[1.55]">
          This step hasn&apos;t started yet. It will activate when its predecessor completes.
        </div>
      )}

      {sub.status === "running" && (
        <div>
          <div
            className="p-[12px_14px] mb-4 rounded-[6px] text-[13px] leading-[1.5] text-ink-2"
            style={{
              background: "var(--color-purple-soft)",
              borderLeft: "3px solid var(--color-purple)",
            }}
          >
            <strong style={{ color: "var(--color-purple)" }}>Agent reasoning:</strong>{" "}
            The {sub.name.toLowerCase()} stage is in progress.
          </div>

          {sub.id === 4 && (
            <>
              <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-2 mb-2 font-semibold">
                Tagging progress
              </div>
              <div className="bg-white border border-rule rounded-[8px] p-4 mb-4">
                <div className="h-2 rounded-full overflow-hidden" style={{ background: "var(--color-rule)" }}>
                  <div
                    className="h-full transition-all duration-700 rounded-full"
                    style={{
                      width: `${progress}%`,
                      background: "linear-gradient(90deg, var(--color-purple), var(--color-pink))",
                    }}
                  />
                </div>
                <div className="flex justify-between mt-2 font-mono text-[10px]">
                  <span className="text-muted">{analyzedRows} / {rowCount} rows</span>
                  <span className="text-purple font-medium">{progress}%</span>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {sub.status === "review" && (
        <div>
          <div
            className="p-[12px_14px] mb-4 rounded-[6px] text-[13px] leading-[1.5] text-ink-2"
            style={{
              background: "var(--color-amber-soft, #fff7e0)",
              borderLeft: "3px solid var(--color-amber)",
            }}
          >
            <strong style={{ color: "var(--color-amber)" }}>Checkpoint:</strong>{" "}
            The {sub.name.toLowerCase()} sub-agent finished. Review the result, then
            approve to continue or send feedback to refine this step.
          </div>

          {sub.result && typeof sub.result === "object" && (
            <>
              <SectionLabel>Sub-agent result</SectionLabel>
              <pre
                className="bg-white border border-rule rounded-[8px] p-3 mb-4 text-[12px] leading-[1.5] text-ink-2 overflow-x-auto whitespace-pre-wrap"
                style={{ maxHeight: 220 }}
              >
                {JSON.stringify(sub.result, null, 2)}
              </pre>
            </>
          )}

          {isCheckpointed && (
            <div className="flex flex-col gap-3">
              <div className="flex gap-2">
                <button
                  onClick={onApprove}
                  disabled={continueBusy}
                  className="px-4 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.12em] font-medium text-white inline-flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                  style={{
                    background: "linear-gradient(135deg, var(--color-purple), var(--color-pink))",
                    boxShadow: "0 3px 10px rgba(108,76,255,0.25)",
                  }}
                >
                  <span>Good to go ✓</span>
                </button>
                <button
                  onClick={() => setRefineOpen(!refineOpen)}
                  disabled={continueBusy}
                  className="px-4 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.12em] font-medium border border-rule text-ink-3 hover:text-purple hover:border-purple-rule hover:bg-purple-soft transition-all disabled:opacity-40"
                >
                  Refine with feedback ↻
                </button>
              </div>

              {refineOpen && (
                <div className="bg-white border border-rule rounded-[8px] p-3">
                  <textarea
                    value={refineText}
                    onChange={e => setRefineText(e.target.value)}
                    rows={3}
                    placeholder="What should this sub-agent do differently?"
                    className="w-full px-3 py-2 text-[13px] border border-rule rounded-[6px] bg-paper focus:border-purple focus:bg-white focus:shadow-[0_0_0_3px_var(--color-purple-soft)] outline-none transition-all resize-none"
                    style={{ fontFamily: "var(--font-display)" }}
                  />
                  <div className="flex justify-end mt-2">
                    <button
                      onClick={onRefineSubmit}
                      disabled={continueBusy || !refineText.trim()}
                      className="px-4 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.12em] font-medium text-white inline-flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                      style={{
                        background: "linear-gradient(135deg, var(--color-purple), var(--color-pink))",
                      }}
                    >
                      Submit refinement
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {sub.status === "complete" && (
        <CompleteContent
          sub={sub}
          rowCount={rowCount}
          taggedData={taggedData}
          report={report}
          sessionId={sessionId}
          runStatus={runStatus}
          onViewReport={onViewReport}
        />
      )}
    </div>
  );
}

function CompleteContent({
  sub,
  rowCount,
  taggedData,
  report,
  sessionId,
  runStatus,
  onViewReport,
}: {
  sub: SubAgent;
  rowCount: number;
  taggedData: Record<string, unknown>[];
  report: Record<string, unknown> | null;
  sessionId: string;
  runStatus: RunStatus;
  onViewReport: () => void;
}) {
  const result = (sub.result || {}) as Record<string, unknown>;

  /* ── Sanitization (2) ─ */
  if (sub.id === 2) {
    const original = (result.original_rows ?? result.rows ?? rowCount) as number;
    const cleaned = (result.cleaned_rows ?? result.remaining ?? rowCount) as number;
    const dups = (result.duplicates_removed ?? (Number(original) - Number(cleaned))) as number;
    const reduction = original ? Math.round(((Number(original) - Number(cleaned)) / Number(original)) * 100) : 0;
    return (
      <>
        <Reasoning text={`Cleaned ${original} → ${cleaned} rows. Removed ${dups} duplicate / noise rows.`} />
        <StatRow
          stats={[
            { n: String(original), label: "Original" },
            { n: String(cleaned), label: "Cleaned", tone: "green" },
            { n: String(dups), label: "Removed", tone: "pink" },
            { n: `${reduction}%`, label: "Reduction", tone: "purple" },
          ]}
        />
      </>
    );
  }

  /* ── Schema (3) ─ */
  if (sub.id === 3) {
    const skill = (result.skill_id || result.selected_skill || result.skill || "—") as string;
    const mapping = (result.column_mapping || result.mapping || {}) as Record<string, string>;
    return (
      <>
        <Reasoning text={`Selected skill "${String(skill)}" and mapped columns to the analysis schema.`} />
        <SectionLabel>Selected skill</SectionLabel>
        <div className="bg-white border border-rule rounded-[8px] p-[12px_14px] mb-4 text-[13px] text-ink-2">
          {String(skill)}
        </div>
        {Object.keys(mapping).length > 0 && (
          <>
            <SectionLabel>Column mapping</SectionLabel>
            <div className="bg-white border border-rule rounded-[8px] p-[12px_14px] mb-4">
              <table className="w-full text-[12px]">
                <thead>
                  <tr>
                    <Th>Field</Th>
                    <Th>Column</Th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(mapping).map(([k, v]) => (
                    <tr key={k}>
                      <Td>{k}</Td>
                      <Td>{String(v)}</Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </>
    );
  }

  /* ── Tagging (4) / Tag validation (5) ─ */
  if (sub.id === 4 || sub.id === 5) {
    const tagged = (result.tagged_rows ?? taggedData.length ?? rowCount) as number;
    const sample = taggedData.slice(0, 5);
    const keys = sample[0] ? Object.keys(sample[0]).slice(0, 4) : [];
    return (
      <>
        <Reasoning text={`Tagged ${tagged} rows with the configured schema.`} />
        <StatRow
          stats={[
            { n: String(tagged), label: "Tagged", tone: "green" },
            { n: String(rowCount), label: "Total" },
            {
              n: rowCount ? `${Math.round((Number(tagged) / rowCount) * 100)}%` : "—",
              label: "Coverage",
              tone: "purple",
            },
          ]}
        />
        {sample.length > 0 && (
          <>
            <SectionLabel>Sample tagged rows · {sample.length} of {taggedData.length}</SectionLabel>
            <div className="bg-white border border-rule rounded-[8px] p-[12px_14px] mb-4 overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr>
                    {keys.map(k => (
                      <Th key={k}>{k}</Th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sample.map((row, i) => (
                    <tr key={i}>
                      {keys.map(k => (
                        <Td key={k}>{truncate(row[k])}</Td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </>
    );
  }

  /* ── Patterns (6) ─ */
  if (sub.id === 6) {
    const themes = ((result.themes || result.top_themes || []) as Array<{ name?: string; label?: string; count?: number; share?: number }>);
    return (
      <>
        <Reasoning text="Identified the top themes and patterns from the tagged data." />
        {themes.length > 0 ? (
          <div className="bg-white border border-rule rounded-[8px] p-[12px_14px] mb-4">
            {themes.slice(0, 8).map((t, i) => {
              const name = t.name || t.label || `Theme ${i + 1}`;
              const share = t.share ?? (t.count ? Math.round((t.count / (themes.reduce((a, x) => a + (x.count || 0), 0) || 1)) * 100) : 0);
              return (
                <div key={i} className="mb-2.5 last:mb-0">
                  <div className="flex justify-between text-[12px] mb-1">
                    <span className="text-ink-2">{name}</span>
                    <span className="font-mono text-muted">{share}%</span>
                  </div>
                  <div className="h-1.5 rounded-full" style={{ background: "var(--color-rule)" }}>
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${share}%`,
                        background: "linear-gradient(90deg, var(--color-purple), var(--color-pink))",
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-[13px] text-muted">Pattern analysis complete.</div>
        )}
      </>
    );
  }

  /* ── Insights (7) ─ */
  if (sub.id === 7) {
    const toolReport = (result.report || {}) as Record<string, unknown>;
    const findings = ((report?.findings || (toolReport.findings as unknown[]) || result.findings || []) as Array<Record<string, unknown>>);
    const evidence = ((report?.evidence || (toolReport.evidence as unknown[]) || result.evidence || []) as Array<Record<string, unknown>>);
    return (
      <>
        <Reasoning text={`Generated ${findings.length} findings with supporting evidence.`} />
        {findings.length > 0 && (
          <>
            <SectionLabel>Findings</SectionLabel>
            {findings.slice(0, 4).map((f, i) => (
              <div key={i} className="bg-white border border-rule rounded-[8px] p-4 mb-3">
                <div className="text-[14px] text-ink leading-[1.45] mb-2"
                  style={{ fontFamily: "var(--font-display)" }}>
                  {String(f.claim || f.title || f.text || "")}
                </div>
                {f.support ? (
                  <div className="text-[12px] text-muted leading-[1.55]">{String(f.support)}</div>
                ) : null}
              </div>
            ))}
          </>
        )}
        {evidence.length > 0 && (
          <>
            <SectionLabel>Evidence · {evidence.length} cited</SectionLabel>
            <div className="bg-white border border-rule rounded-[8px] p-[12px_14px] mb-4">
              {evidence.slice(0, 3).map((ev, i) => (
                <div key={i} className="border-b border-rule last:border-b-0 py-2.5 first:pt-0 last:pb-0">
                  <div className="font-mono text-[10px] text-muted uppercase tracking-[0.08em] mb-1">
                    {String(ev.source || "—")}
                  </div>
                  <div
                    className="text-[13px] text-ink-2 italic leading-[1.5]"
                    style={{ fontFamily: "var(--font-display)" }}
                  >
                    &ldquo;{String(ev.quote || "")}&rdquo;
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </>
    );
  }

  /* ── Design (8) ─ */
  if (sub.id === 8) {
    return (
      <>
        <Reasoning text="Applied design and styling to the report based on the chosen theme." />
        <div className="text-[13px] text-muted">Design pass complete.</div>
      </>
    );
  }

  /* ── Render / export (9) ─ */
  if (sub.id === 9) {
    return (
      <>
        <Reasoning text="Report rendered. Export below or open in workbench." />
        <SectionLabel>Export</SectionLabel>
        <div className="flex flex-wrap gap-2 mb-4">
          <ExportBtn href={`${BASE}/session/${sessionId}/export/html-report`} primary>
            HTML report
          </ExportBtn>
          <ExportBtn href={`${BASE}/session/${sessionId}/export/pptx-report`} primary>
            PPTX
          </ExportBtn>
          <ExportBtn href={`${BASE}/session/${sessionId}/export/csv`}>CSV</ExportBtn>
          <ExportBtn href={`${BASE}/session/${sessionId}/export/xlsx`}>XLSX</ExportBtn>
        </div>
        {runStatus === "complete" && (
          <div className="flex gap-2 pt-4 border-t border-rule">
            <button
              onClick={onViewReport}
              className="px-3.5 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.12em] font-medium border border-rule text-ink-3 hover:text-purple hover:border-purple-rule hover:bg-purple-soft transition-all"
            >
              Open in workbench
            </button>
          </div>
        )}
      </>
    );
  }

  /* ── Default (1 - data acquisition, fallbacks) ─ */
  return (
    <>
      <Reasoning text={`Step ${sub.name} completed.`} />
      {sub.id === 1 && rowCount > 0 && (
        <StatRow
          stats={[
            { n: String(rowCount), label: "Rows" },
          ]}
        />
      )}
    </>
  );
}

/* ── small UI atoms ───────────────────────────────────────────────── */

function Reasoning({ text }: { text: string }) {
  return (
    <div
      className="p-[12px_14px] mb-4 rounded-[6px] text-[13px] leading-[1.5] text-ink-2"
      style={{
        background: "var(--color-purple-soft)",
        borderLeft: "3px solid var(--color-purple)",
      }}
    >
      <strong style={{ color: "var(--color-purple)" }}>Agent reasoning:</strong> {text}
    </div>
  );
}

function StatRow({
  stats,
}: {
  stats: Array<{ n: string; label: string; tone?: "green" | "pink" | "purple" }>;
}) {
  return (
    <div
      className="grid gap-2.5 mb-4"
      style={{ gridTemplateColumns: `repeat(${Math.min(stats.length, 4)}, 1fr)` }}
    >
      {stats.map((s, i) => (
        <div key={i} className="bg-white border border-rule rounded-[8px] p-[12px_14px]">
          <div
            className="text-[22px] font-medium leading-none tracking-[-0.02em]"
            style={{
              fontFamily: "var(--font-display)",
              color:
                s.tone === "green"
                  ? "var(--color-green)"
                  : s.tone === "pink"
                  ? "var(--color-pink)"
                  : s.tone === "purple"
                  ? "var(--color-purple)"
                  : "var(--color-ink)",
            }}
          >
            {s.n}
          </div>
          <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted mt-1">
            {s.label}
          </div>
        </div>
      ))}
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-2 mb-2 font-semibold">
      {children}
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="text-left font-mono text-[9px] uppercase tracking-[0.1em] text-muted-2 py-[6px] px-2 border-b border-rule font-medium">
      {children}
    </th>
  );
}

function Td({ children }: { children: React.ReactNode }) {
  return (
    <td className="py-[7px] px-2 border-b border-rule text-ink-2 text-[12px] last:border-b-0">
      {children}
    </td>
  );
}

function ExportBtn({
  href,
  primary,
  children,
}: {
  href: string;
  primary?: boolean;
  children: React.ReactNode;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`px-3.5 py-2 rounded-[6px] font-mono text-[10px] uppercase tracking-[0.12em] font-medium inline-flex items-center gap-1.5 transition-all no-underline ${
        primary
          ? "text-white"
          : "border border-rule text-ink-3 hover:text-purple hover:border-purple-rule hover:bg-purple-soft"
      }`}
      style={
        primary
          ? {
              background: "linear-gradient(135deg, var(--color-purple), var(--color-pink))",
              boxShadow: "0 3px 10px rgba(108,76,255,0.25)",
            }
          : undefined
      }
    >
      {children}
    </a>
  );
}

/* ── utils ────────────────────────────────────────────────────────── */

function truncate(v: unknown, max = 40): string {
  if (v == null) return "—";
  const s = String(v);
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}
