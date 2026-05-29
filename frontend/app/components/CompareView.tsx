"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  listSessions,
  compareRuns,
  type SessionInfo,
  type ComparisonResult,
  type CompareRun,
} from "../lib/api";

interface CompareViewProps {
  onGoToAgents: () => void;
}

const AGENT_LABELS: Record<string, { name: string; initials: string; gradient: string }> = {
  explainable_ai_tagging: { name: "Brand Insights",       initials: "BI", gradient: "from-purple to-pink" },
  genz_brand_tracker:     { name: "Competitive Intel",    initials: "CI", gradient: "from-pink to-orange-400" },
  pharma_social_intelligence: { name: "Pharma SI",        initials: "PS", gradient: "from-sky-500 to-purple" },
};

function agentMeta(id: string) {
  return AGENT_LABELS[id] || {
    name: id.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()),
    initials: (id.slice(0, 2) || "AG").toUpperCase(),
    gradient: "from-slate-500 to-slate-700",
  };
}

const CONFIDENCE_COLOR: Record<string, string> = {
  high:   "bg-emerald-100 text-emerald-700",
  medium: "bg-amber-100 text-amber-700",
  low:    "bg-slate-100 text-slate-600",
};

const SENT_COLOR: Record<string, string> = {
  Positive: "bg-emerald-50 text-emerald-700 border-emerald-200",
  Negative: "bg-red-50 text-red-700 border-red-200",
  Neutral:  "bg-slate-50 text-slate-600 border-slate-200",
  Mixed:    "bg-amber-50 text-amber-700 border-amber-200",
};

// ── Agent icon ────────────────────────────────────────────────────────────────
function AgentBadge({ agentId, size = 28 }: { agentId: string; size?: number }) {
  const meta = agentMeta(agentId);
  return (
    <div
      className={`rounded-full bg-gradient-to-br ${meta.gradient} text-white font-mono font-medium flex items-center justify-center flex-shrink-0`}
      style={{ width: size, height: size, fontSize: Math.max(9, size * 0.4) }}
      title={meta.name}
    >
      {meta.initials}
    </div>
  );
}

// ── Bar chart for themes/sentiments ───────────────────────────────────────────
function BarChart({
  items,
  max,
  highlight,
}: {
  items: { name: string; count: number }[];
  max: number;
  highlight?: (name: string) => "convergent" | "divergent" | null;
}) {
  if (items.length === 0) {
    return <div className="font-mono text-[10px] text-muted">No data</div>;
  }
  return (
    <div className="flex flex-col gap-1.5">
      {items.map(item => {
        const pct = max > 0 ? (item.count / max) * 100 : 0;
        const tag = highlight ? highlight(item.name) : null;
        const barColor =
          tag === "convergent"
            ? "bg-emerald-400"
            : tag === "divergent"
            ? "bg-amber-400"
            : "bg-gradient-to-r from-purple to-pink";
        return (
          <div key={item.name} className="flex items-center gap-2">
            <div className="text-[11px] text-ink-3 truncate flex-1 min-w-0" title={item.name}>
              {item.name}
            </div>
            <div className="flex-1 h-2 bg-paper-2 rounded overflow-hidden min-w-[40px]">
              <div className={`h-full ${barColor}`} style={{ width: `${pct}%` }} />
            </div>
            <div className="font-mono text-[10px] text-muted w-7 text-right">{item.count}</div>
          </div>
        );
      })}
    </div>
  );
}

// ── Sentiment stacked bar ─────────────────────────────────────────────────────
function SentimentBar({ items }: { items: { name: string; count: number }[] }) {
  const total = items.reduce((s, i) => s + i.count, 0);
  if (total === 0) return <div className="font-mono text-[10px] text-muted">No data</div>;
  const colorFor = (name: string) =>
    name === "Positive" ? "bg-emerald-400" :
    name === "Negative" ? "bg-red-400" :
    name === "Mixed"    ? "bg-amber-400" :
                          "bg-slate-300";
  return (
    <div className="flex flex-col gap-2">
      <div className="flex h-3 rounded overflow-hidden border border-rule">
        {items.map(it => (
          <div
            key={it.name}
            className={colorFor(it.name)}
            style={{ width: `${(it.count / total) * 100}%` }}
            title={`${it.name}: ${it.count}`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map(it => (
          <span
            key={it.name}
            className={`font-mono text-[9px] px-1.5 py-0.5 rounded border ${SENT_COLOR[it.name] || "bg-slate-50 text-slate-600 border-slate-200"}`}
          >
            {it.name} {it.count}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Skeleton column for loading state ─────────────────────────────────────────
function SkeletonColumn() {
  return (
    <div className="border border-rule rounded-[10px] p-4 bg-white animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-7 h-7 rounded-full bg-paper-2" />
        <div className="flex-1 h-3 bg-paper-2 rounded" />
      </div>
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-2 bg-paper-2 rounded mb-2" style={{ width: `${100 - i * 12}%` }} />
      ))}
    </div>
  );
}

// ── Single comparison column ──────────────────────────────────────────────────
function CompareColumn({
  run,
  convergentThemes,
  totalRuns,
}: {
  run: CompareRun;
  convergentThemes: Set<string>;
  totalRuns: number;
}) {
  const meta = agentMeta(run.agent);
  const themeMax = run.themes.reduce((m, t) => Math.max(m, t.count), 0);
  const allDivergent = run.themes.every(
    t => !convergentThemes.has(t.name.toLowerCase()),
  );
  // Subtle column tint: green glow if it shares >50% themes with others,
  // amber tint if it has no shared themes at all (a clear outlier).
  const sharedCount = run.themes.filter(t => convergentThemes.has(t.name.toLowerCase())).length;
  const ringClass =
    totalRuns >= 2 && sharedCount >= Math.ceil(run.themes.length / 2) && sharedCount > 0
      ? "ring-1 ring-emerald-200 shadow-[0_0_0_4px_rgba(16,185,129,0.06)]"
      : totalRuns >= 2 && allDivergent
      ? "ring-1 ring-amber-200 shadow-[0_0_0_4px_rgba(245,158,11,0.05)]"
      : "";

  return (
    <div className={`border border-rule rounded-[10px] bg-white flex flex-col min-w-0 ${ringClass}`}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-rule">
        <div className="flex items-center gap-2.5">
          <AgentBadge agentId={run.agent} size={32} />
          <div className="min-w-0 flex-1">
            <div className="text-[13px] font-medium text-ink truncate" style={{ fontFamily: "var(--font-display)" }}>
              {meta.name}
            </div>
            <div className="font-mono text-[10px] text-muted truncate" title={run.filename}>
              {run.filename}
            </div>
          </div>
        </div>
      </div>

      {/* Executive one-liner */}
      <div className="px-4 py-3 border-b border-rule">
        <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-2 mb-1.5">
          Executive read
        </div>
        <p className="text-[12.5px] text-ink leading-[1.45]">
          {run.executive_one_liner || run.subtitle || "—"}
        </p>
      </div>

      {/* Top findings */}
      <div className="px-4 py-3 border-b border-rule">
        <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-2 mb-2">
          Top findings
        </div>
        {run.findings.length === 0 ? (
          <div className="font-mono text-[10px] text-muted">No findings</div>
        ) : (
          <ul className="flex flex-col gap-2">
            {run.findings.map((f, i) => (
              <li key={i} className="flex gap-2 items-start">
                <span className="font-mono text-[9px] text-muted-2 mt-0.5">{i + 1}.</span>
                <div className="flex-1 min-w-0">
                  <div className="text-[11.5px] text-ink leading-[1.4]">{f.claim || "—"}</div>
                  <span className={`mt-1 inline-block font-mono text-[8.5px] uppercase tracking-[0.08em] px-1.5 py-0.5 rounded ${CONFIDENCE_COLOR[f.confidence] || CONFIDENCE_COLOR.medium}`}>
                    {f.confidence}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Themes bar chart */}
      <div className="px-4 py-3 border-b border-rule">
        <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-2 mb-2">
          Top themes
        </div>
        <BarChart
          items={run.themes}
          max={themeMax}
          highlight={name =>
            convergentThemes.has(name.toLowerCase()) ? "convergent" : "divergent"
          }
        />
      </div>

      {/* Sentiment mix */}
      <div className="px-4 py-3 border-b border-rule">
        <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-2 mb-2">
          Sentiment / voice mix
        </div>
        <SentimentBar items={run.sentiments} />
      </div>

      {/* Evidence quotes */}
      <div className="px-4 py-3 border-b border-rule">
        <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-2 mb-2">
          Top evidence
        </div>
        {run.evidence.length === 0 ? (
          <div className="font-mono text-[10px] text-muted">No evidence</div>
        ) : (
          <ul className="flex flex-col gap-2">
            {run.evidence.map((e, i) => (
              <li key={i} className="border-l-2 border-rule pl-2.5">
                <p className="text-[11.5px] text-ink leading-[1.45] italic">&ldquo;{e.quote}&rdquo;</p>
                {(e.sentiment || e.source) && (
                  <div className="font-mono text-[9px] text-muted mt-1 flex gap-2">
                    {e.sentiment && <span>{e.sentiment}</span>}
                    {e.source && <span className="truncate" title={e.source}>{e.source}</span>}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Recommendations */}
      <div className="px-4 py-3 flex-1">
        <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-2 mb-2">
          So-what recommendations
        </div>
        {run.recommendations.length === 0 ? (
          <div className="font-mono text-[10px] text-muted">No recommendations</div>
        ) : (
          <ol className="flex flex-col gap-1.5 list-decimal list-inside">
            {run.recommendations.map((r, i) => (
              <li key={i} className="text-[11.5px] text-ink leading-[1.45]">{r}</li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

// ── Build a downloadable HTML summary ─────────────────────────────────────────
function buildExportHtml(result: ComparisonResult): string {
  const esc = (s: string) =>
    String(s).replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]!));
  const colCount = result.runs.length;
  const colsHtml = result.runs.map(run => {
    const meta = agentMeta(run.agent);
    const findings = run.findings
      .map((f, i) => `<li><strong>${esc(f.claim)}</strong> <em>(${esc(f.confidence)})</em></li>`)
      .join("");
    const themes = run.themes
      .map(t => `<li>${esc(t.name)} <span style="color:#888">— ${t.count}</span></li>`)
      .join("");
    const evidence = run.evidence
      .map(e => `<blockquote style="border-left:3px solid #ddd;padding-left:8px;margin:4px 0;color:#333">"${esc(e.quote)}"<br><small>${esc(e.sentiment)} · ${esc(e.source)}</small></blockquote>`)
      .join("");
    const recs = run.recommendations.map(r => `<li>${esc(r)}</li>`).join("");
    return `<td style="vertical-align:top;padding:12px;border:1px solid #eee;width:${100 / colCount}%">
      <h3 style="margin:0 0 4px">${esc(meta.name)}</h3>
      <p style="color:#888;margin:0 0 12px;font-size:12px">${esc(run.filename)}</p>
      <p><em>${esc(run.executive_one_liner || run.subtitle)}</em></p>
      <h4>Top findings</h4><ol>${findings}</ol>
      <h4>Top themes</h4><ul>${themes}</ul>
      <h4>Evidence</h4>${evidence}
      <h4>Recommendations</h4><ol>${recs}</ol>
    </td>`;
  }).join("");

  return `<!doctype html><html><head><meta charset="utf-8">
<title>Multi-agent comparison report</title>
<style>body{font-family:-apple-system,system-ui,sans-serif;max-width:1400px;margin:24px auto;padding:0 16px;color:#1c1a16}
table{border-collapse:collapse;width:100%}h1{margin:0 0 4px}h4{margin:14px 0 6px;color:#555}
.synth{background:#f8f6ff;border-left:4px solid #6c4cff;padding:14px;border-radius:6px;margin:18px 0}
</style></head><body>
<h1>Multi-agent comparison</h1>
<p style="color:#888">Generated ${new Date().toLocaleString()} · ${result.runs.length} runs</p>
<div class="synth"><strong>Synthesis</strong><p>${esc(result.synthesis)}</p></div>
<table><tr>${colsHtml}</tr></table>
</body></html>`;
}

// ══════════════════════════════════════════════════════════════════════════════
// Main view
// ══════════════════════════════════════════════════════════════════════════════
export default function CompareView({ onGoToAgents }: CompareViewProps) {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [selected, setSelected] = useState<string[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch available sessions
  useEffect(() => {
    let cancelled = false;
    listSessions()
      .then(data => {
        if (cancelled) return;
        // Only show completed sessions with a report
        const eligible = data.sessions.filter(s => s.has_report || s.analyzed_count > 0);
        setSessions(eligible);
      })
      .catch(() => {
        if (!cancelled) setSessions([]);
      })
      .finally(() => {
        if (!cancelled) setSessionsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Picker dropdown — close on outside click / escape
  useEffect(() => {
    if (!pickerOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPickerOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pickerOpen]);

  const selectedSessions = useMemo(
    () => selected.map(id => sessions.find(s => s.session_id === id)).filter((s): s is SessionInfo => !!s),
    [selected, sessions],
  );

  const toggleSelect = useCallback((id: string) => {
    setSelected(prev => {
      if (prev.includes(id)) return prev.filter(x => x !== id);
      if (prev.length >= 4) return prev; // max 4
      return [...prev, id];
    });
  }, []);

  const removeSelected = useCallback((id: string) => {
    setSelected(prev => prev.filter(x => x !== id));
    // Invalidate stale result if its set differs
    setResult(prev => (prev && prev.runs.some(r => r.session_id === id) ? null : prev));
  }, []);

  const runCompare = useCallback(async () => {
    if (selected.length < 2) return;
    setComparing(true);
    setError(null);
    setResult(null);
    try {
      const data = await compareRuns(selected);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed");
    } finally {
      setComparing(false);
    }
  }, [selected]);

  const exportComparison = useCallback(() => {
    if (!result) return;
    const html = buildExportHtml(result);
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `comparison-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [result]);

  // Build convergent-theme set (themes appearing in 2+ runs)
  const convergentThemes = useMemo(() => {
    if (!result) return new Set<string>();
    return new Set(result.overlaps.themes.map(t => t.name.toLowerCase()));
  }, [result]);

  // ── Empty state: no completed runs ────────────────────────────────────────
  if (!sessionsLoading && sessions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-32 text-center px-6">
        <div className="w-12 h-12 rounded-full bg-paper-2 flex items-center justify-center mb-4">
          <svg width="22" height="22" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" className="text-muted">
            <rect x="2" y="3" width="7" height="9" rx="1" />
            <rect x="7" y="6" width="7" height="9" rx="1" />
          </svg>
        </div>
        <p className="text-[15px] text-ink mb-2" style={{ fontFamily: "var(--font-display)" }}>
          No completed runs yet — run an agent first
        </p>
        <p className="text-[12.5px] text-muted max-w-[420px] mb-5">
          Once you have at least two completed agent runs, you can compare their findings side-by-side here.
        </p>
        <button
          onClick={onGoToAgents}
          className="py-2 px-4 rounded-[8px] font-mono text-[11px] font-medium uppercase tracking-[0.1em] text-white bg-gradient-to-r from-purple to-pink hover:shadow-[0_4px_16px_rgba(108,76,255,0.25)] transition-all"
        >
          Go to Agents
        </button>
      </div>
    );
  }

  const canCompare = selected.length >= 2 && !comparing;

  return (
    <div className="flex flex-col min-h-[calc(100vh-53px)]">
      {/* Sticky picker bar */}
      <div className="sticky top-[53px] z-10 bg-paper/85 backdrop-blur-[14px] border-b border-rule px-8 py-4">
        <div className="flex items-start gap-4 flex-wrap">
          <div className="flex-1 min-w-[280px]">
            <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-2 mb-1.5">
              Select runs to compare
            </div>
            <div className="flex items-start gap-2 flex-wrap">
              {/* Chips */}
              {selectedSessions.map(s => {
                const meta = agentMeta(s.report_type || "");
                return (
                  <div
                    key={s.session_id}
                    className="flex items-center gap-2 pl-1.5 pr-2 py-1 bg-white border border-rule rounded-full"
                  >
                    <AgentBadge agentId={s.report_type || ""} size={18} />
                    <span className="text-[12px] text-ink">{meta.name}</span>
                    <span className="font-mono text-[10px] text-muted truncate max-w-[140px]" title={s.filename || ""}>
                      {s.filename || s.session_id.slice(0, 6)}
                    </span>
                    <button
                      onClick={() => removeSelected(s.session_id)}
                      className="w-4 h-4 rounded-full flex items-center justify-center text-muted hover:text-pink hover:bg-pink-soft transition-colors"
                      aria-label="Remove"
                    >
                      <svg width="8" height="8" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M2 2l8 8M10 2l-8 8" />
                      </svg>
                    </button>
                  </div>
                );
              })}

              {/* Multi-select dropdown trigger */}
              <div className="relative">
                <button
                  onClick={() => setPickerOpen(p => !p)}
                  disabled={selected.length >= 4}
                  className="py-1 px-3 rounded-full border border-dashed border-rule text-[12px] text-muted hover:text-ink hover:border-purple-rule transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {selected.length >= 4 ? "Max 4 selected" : "+ Add run"}
                </button>
                {pickerOpen && (
                  <>
                    <div className="fixed inset-0 z-30" onClick={() => setPickerOpen(false)} />
                    <div className="absolute left-0 top-[110%] z-40 w-[360px] max-h-[360px] overflow-y-auto bg-white border border-rule rounded-[8px] shadow-[0_8px_28px_rgba(20,19,42,0.12)]">
                      {sessionsLoading ? (
                        <div className="px-3 py-3 font-mono text-[11px] text-muted">Loading runs...</div>
                      ) : (
                        sessions.map(s => {
                          const meta = agentMeta(s.report_type || "");
                          const isSelected = selected.includes(s.session_id);
                          const isFull = selected.length >= 4 && !isSelected;
                          return (
                            <button
                              key={s.session_id}
                              onClick={() => !isFull && toggleSelect(s.session_id)}
                              disabled={isFull}
                              className={`w-full text-left flex items-center gap-2 px-3 py-2 border-b border-rule last:border-b-0 hover:bg-paper-2 transition-colors ${isFull ? "opacity-40 cursor-not-allowed" : ""}`}
                            >
                              <span className={`w-3.5 h-3.5 border rounded flex items-center justify-center flex-shrink-0 ${isSelected ? "bg-purple border-purple" : "border-rule"}`}>
                                {isSelected && (
                                  <svg width="9" height="9" viewBox="0 0 12 12" fill="none" stroke="white" strokeWidth="2.4">
                                    <path d="M2 6l3 3 5-6" />
                                  </svg>
                                )}
                              </span>
                              <AgentBadge agentId={s.report_type || ""} size={20} />
                              <div className="min-w-0 flex-1">
                                <div className="text-[12px] text-ink truncate">{meta.name}</div>
                                <div className="font-mono text-[10px] text-muted truncate">{s.filename || s.session_id.slice(0, 8)}</div>
                              </div>
                              {s.is_demo && (
                                <span className="font-mono text-[9px] px-1.5 py-0.5 bg-purple-soft text-purple rounded">DEMO</span>
                              )}
                            </button>
                          );
                        })
                      )}
                      {!sessionsLoading && sessions.length === 0 && (
                        <div className="px-3 py-3 font-mono text-[11px] text-muted">No runs available</div>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 mt-[18px]">
            <button
              onClick={runCompare}
              disabled={!canCompare}
              className="py-2 px-4 rounded-[8px] font-mono text-[11px] font-medium uppercase tracking-[0.1em] text-white bg-gradient-to-r from-purple to-pink hover:shadow-[0_4px_16px_rgba(108,76,255,0.25)] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {comparing ? "Comparing..." : "Compare"}
            </button>
            <button
              onClick={exportComparison}
              disabled={!result}
              className="py-2 px-4 rounded-[8px] font-mono text-[11px] font-medium uppercase tracking-[0.1em] text-purple border border-purple-rule hover:bg-purple-soft transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Export comparison
            </button>
          </div>
        </div>
        {error && (
          <div className="mt-3 font-mono text-[11px] text-pink bg-pink-soft px-3 py-2 rounded-[6px]">
            {error}
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 px-8 py-6">
        {/* Loading skeletons */}
        {comparing && (
          <div
            className="grid gap-4"
            style={{
              gridTemplateColumns: `repeat(${Math.max(selected.length, 2)}, minmax(0, 1fr))`,
            }}
          >
            {Array.from({ length: Math.max(selected.length, 2) }).map((_, i) => (
              <SkeletonColumn key={i} />
            ))}
          </div>
        )}

        {/* No selection state */}
        {!comparing && !result && selected.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <p className="text-[14px] text-muted" style={{ fontFamily: "var(--font-display)" }}>
              Pick 2-4 runs above to compare them side-by-side.
            </p>
          </div>
        )}

        {/* Selected but not yet compared */}
        {!comparing && !result && selected.length > 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <p className="text-[14px] text-muted mb-2" style={{ fontFamily: "var(--font-display)" }}>
              {selected.length === 1
                ? "Pick at least one more run, then hit Compare."
                : `${selected.length} runs selected — hit Compare to see the side-by-side.`}
            </p>
          </div>
        )}

        {/* Results */}
        {!comparing && result && (
          <>
            <div
              className="grid gap-4"
              style={{
                gridTemplateColumns: `repeat(${result.runs.length}, minmax(280px, 1fr))`,
              }}
            >
              {result.runs.map(run => (
                <CompareColumn
                  key={run.session_id}
                  run={run}
                  convergentThemes={convergentThemes}
                  totalRuns={result.runs.length}
                />
              ))}
            </div>

            {/* Overlaps summary */}
            {(result.overlaps.themes.length > 0 || result.divergences.length > 0) && (
              <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                {result.overlaps.themes.length > 0 && (
                  <div className="border border-emerald-200 bg-emerald-50/40 rounded-[10px] p-4">
                    <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-emerald-700 mb-2">
                      Agreements — themes in 2+ runs
                    </div>
                    <ul className="flex flex-wrap gap-1.5">
                      {result.overlaps.themes.map(t => (
                        <li
                          key={t.name}
                          className="font-mono text-[10px] px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded"
                        >
                          {t.name} · {t.run_count}/{result.runs.length}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {result.divergences.length > 0 && (
                  <div className="border border-amber-200 bg-amber-50/40 rounded-[10px] p-4">
                    <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-amber-700 mb-2">
                      Divergences — themes only in one run
                    </div>
                    <ul className="flex flex-wrap gap-1.5">
                      {result.divergences.slice(0, 12).map(d => (
                        <li
                          key={`${d.session_id}-${d.name}`}
                          className="font-mono text-[10px] px-2 py-0.5 bg-amber-100 text-amber-700 rounded"
                          title={agentMeta(d.agent).name}
                        >
                          {d.name}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Synthesis bar */}
            <div className="mt-6 border border-purple-rule bg-purple-soft/60 rounded-[10px] p-5">
              <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-purple mb-2">
                Synthesis — meta-insight across {result.runs.length} reports
              </div>
              <p className="text-[13px] text-ink leading-[1.55]" style={{ fontFamily: "var(--font-display)" }}>
                {result.synthesis}
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
