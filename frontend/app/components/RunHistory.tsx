"use client";
import { useEffect, useState } from "react";
import { listRuns, getRun, exportUrl } from "../lib/api";

interface RunMeta {
  run_id: string;
  session_id: string;
  filename: string;
  provider: string;
  model: string;
  total_rows: number;
  completed: number;
  elapsed_sec?: number;
  status: string;
  started_at: string;
  completed_at?: string;
}

interface RunDetail extends RunMeta {
  analyzed_data: Record<string, unknown>[];
  columns: string[];
  context?: Record<string, unknown>;
}

interface RunHistoryProps {
  onClose: () => void;
}

const STATUS_COLOR: Record<string, string> = {
  complete:  "bg-emerald-100 text-emerald-700",
  completed: "bg-emerald-100 text-emerald-700",
  running:   "bg-amber-100 text-amber-700",
  error:     "bg-red-100 text-red-600",
};

const AI_KEYS = new Set([
  "theme","sub_theme_1","sub_theme_2","sub_theme_3",
  "sentiment","sentiment_nuance","emotion","driver",
  "severity","signals","confidence",
  "xai_text_evidence","xai_theme_reasoning","xai_sentiment_reasoning",
  "xai_signal_reasoning","xai_confidence_reasoning","error",
]);

const SENT_COLOR: Record<string, string> = {
  Positive: "bg-emerald-100 text-emerald-700",
  Negative: "bg-red-100 text-red-600",
  Neutral:  "bg-gray-100 text-gray-600",
  Mixed:    "bg-amber-100 text-amber-700",
};

// ── Popup types ───────────────────────────────────────────────────────────────
type PopupState =
  | { type: "cell"; col: string; value: string }
  | { type: "xai";  row: Record<string, unknown> };

// ── Unified popup modal ───────────────────────────────────────────────────────
function Popup({ state, onClose }: { state: PopupState; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/40" />
      <div
        className="relative bg-white rounded-2xl shadow-2xl w-full max-w-xl flex flex-col"
        style={{ maxHeight: "80vh" }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#E5E3DC] shrink-0">
          {state.type === "cell" ? (
            <span className="text-[10px] font-bold text-[#7C3AED] uppercase tracking-widest bg-[#EDE9FE] px-2.5 py-1 rounded-full">
              {state.col.replace(/_/g, " ")}
            </span>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold text-[#7C3AED] uppercase tracking-widest bg-[#EDE9FE] px-2.5 py-1 rounded-full">
                ✦ XAI Rationale
              </span>
              <span className="text-[10px] text-[#9CA3AF]">Every decision grounded in source text</span>
            </div>
          )}
          <button
            onClick={onClose}
            className="ml-3 shrink-0 w-7 h-7 flex items-center justify-center rounded-full hover:bg-[#F3F2EE] text-[#9CA3AF] hover:text-[#374151] transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto flex-1 px-5 py-4">
          {state.type === "cell" ? (
            <p className="text-[13px] text-[#374151] leading-relaxed whitespace-pre-wrap break-words">
              {state.value || "—"}
            </p>
          ) : (
            <XAIContent row={state.row} />
          )}
        </div>
      </div>
    </div>
  );
}

// ── XAI content ───────────────────────────────────────────────────────────────
function XAIContent({ row }: { row: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      {Boolean(row.xai_text_evidence) && (
        <div className="bg-[#F9F8FF] border border-[#DDD6FE] rounded-xl p-4">
          <p className="text-[9px] font-bold text-[#7C3AED] uppercase tracking-wider mb-2">📎 Verbatim Text Evidence</p>
          <blockquote className="text-[12px] text-[#374151] italic pl-3 leading-relaxed" style={{ borderLeft: "3px solid #7C3AED" }}>
            &ldquo;{String(row.xai_text_evidence)}&rdquo;
          </blockquote>
        </div>
      )}
      {([
        ["xai_theme_reasoning",     "🏷",  "Theme Reasoning",      "#EDE9FE","#7C3AED"],
        ["xai_sentiment_reasoning", "💬",  "Sentiment Reasoning",  "#DCFCE7","#15803D"],
        ["xai_signal_reasoning",    "⚡",  "Signal Reasoning",     "#FEF3C7","#B45309"],
        ["xai_confidence_reasoning","📊",  "Confidence Reasoning", "#F0F9FF","#0369A1"],
      ] as [string, string, string, string, string][]).map(([key, icon, label, bg, color]) =>
        Boolean(row[key]) ? (
          <div key={key} className="rounded-xl p-4" style={{ backgroundColor: bg }}>
            <p className="text-[9px] font-bold uppercase tracking-wider mb-2" style={{ color }}>
              {icon} {label}
            </p>
            <p className="text-[12px] text-[#374151] leading-relaxed">{String(row[key])}</p>
          </div>
        ) : null
      )}
    </div>
  );
}

// ── Clickable cell ────────────────────────────────────────────────────────────
function Cell({ value, onClick }: { value: string; onClick: () => void }) {
  return (
    <td className="px-3 py-2 cursor-pointer hover:bg-[#F0EBFF] transition-colors group" onClick={onClick}>
      <span className="block truncate max-w-[140px] text-[11px] text-[#374151] group-hover:text-[#7C3AED]">
        {value || <span className="text-[#D1D0CC]">—</span>}
      </span>
    </td>
  );
}

// ── Results workbench ─────────────────────────────────────────────────────────
function RunWorkbench({ run }: { run: RunDetail }) {
  const [popup,      setPopup]      = useState<PopupState | null>(null);
  const [search,     setSearch]     = useState("");
  const [filterSent, setFilterSent] = useState("All sentiments");

  const data = run.analyzed_data ?? [];

  const origCols  = data.length ? Object.keys(data[0]).filter(k => !AI_KEYS.has(k)) : [];
  const textCol   = origCols.find(k => /detail|text|content|body|description|review|title/i.test(k)) ?? origCols[0];
  const sourceCol = origCols.find(k => /source|platform|channel|media.?type/i.test(k));
  const dateCol   = origCols.find(k => /date|time|publish/i.test(k));
  const extraCols = origCols.filter(k => k !== textCol && k !== sourceCol && k !== dateCol);

  const filtered = data.filter(row => {
    if (filterSent !== "All sentiments" && String(row.sentiment) !== filterSent) return false;
    if (search) {
      const q = search.toLowerCase();
      return Object.values(row).some(v => String(v ?? "").toLowerCase().includes(q));
    }
    return true;
  });

  const total    = data.length;
  const positive = data.filter(r => r.sentiment === "Positive").length;
  const negative = data.filter(r => r.sentiment === "Negative").length;
  const avgConf  = total
    ? Math.round(data.reduce((a, r) => a + (Number(r.confidence) || 0), 0) / total * 100)
    : 0;

  const openCell = (col: string, value: unknown) => setPopup({ type: "cell", col, value: String(value ?? "") });
  const openXAI  = (row: Record<string, unknown>) => setPopup({ type: "xai", row });

  if (data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 text-center px-8">
        <svg className="w-10 h-10 text-[#E5E3DC] mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2"/>
        </svg>
        <p className="text-sm font-medium text-[#374151] mb-1">No data stored for this run</p>
        <p className="text-xs text-[#9CA3AF] max-w-xs">This run was completed before per-run file storage was added. Re-run the analysis to get full history access.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {popup && <Popup state={popup} onClose={() => setPopup(null)} />}

      {/* Stats + filters bar */}
      <div className="px-4 py-2 border-b border-[#E5E3DC] bg-white flex items-center gap-4 flex-wrap shrink-0">
        {([
          ["Total",    String(total),                                    "text-[#111827]"],
          ["Positive", `${total ? Math.round(positive/total*100) : 0}%`, "text-emerald-600"],
          ["Negative", `${total ? Math.round(negative/total*100) : 0}%`, "text-red-500"],
          ["Avg Conf", `${avgConf}%`,                                    "text-[#7C3AED]"],
        ] as [string, string, string][]).map(([label, value, color]) => (
          <div key={label} className="text-center">
            <p className={`text-[14px] font-bold leading-none ${color}`}>{value}</p>
            <p className="text-[9px] text-[#9CA3AF] mt-0.5 uppercase tracking-wider">{label}</p>
          </div>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <div className="relative">
            <svg className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-[#9CA3AF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
            <input type="text" value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search…"
              className="pl-7 pr-3 py-1.5 text-[11px] border border-[#E5E3DC] rounded-lg bg-white focus:outline-none focus:border-[#7C3AED] w-40"/>
          </div>
          <select value={filterSent} onChange={e => setFilterSent(e.target.value)}
            className="px-2 py-1.5 text-[11px] border border-[#E5E3DC] rounded-lg bg-white focus:outline-none focus:border-[#7C3AED]">
            {["All sentiments","Positive","Negative","Neutral","Mixed"].map(s => <option key={s}>{s}</option>)}
          </select>
          <a href={exportUrl(run.session_id, "csv")} download
            className="text-[11px] px-3 py-1.5 bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-md transition-colors">
            Export CSV
          </a>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <div className="text-[9px] text-[#9CA3AF] px-4 pt-2 pb-1">
          Click any cell to view full content · Click <span className="text-[#7C3AED] font-medium">✦</span> to view XAI rationale · Scroll right →
          <span className="ml-2">{filtered.length}/{total} rows</span>
        </div>
        <div className="px-4 pb-4">
          <div className="border border-[#E5E3DC] rounded-xl bg-white" style={{ overflowX: "auto" }}>
            <table className="text-[11px] border-collapse" style={{ minWidth: "max-content", width: "100%" }}>
              <thead>
                <tr className="bg-[#F8F7F3] border-b border-[#E5E3DC]">
                  <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#9CA3AF] w-8">#</th>
                  {textCol && <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#9CA3AF] min-w-[160px]">{textCol.replace(/_/g," ")}</th>}
                  {sourceCol && <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#9CA3AF] min-w-[100px]">{sourceCol.replace(/_/g," ")}</th>}
                  {dateCol && <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#9CA3AF] min-w-[90px]">{dateCol.replace(/_/g," ")}</th>}
                  {extraCols.map(col => (
                    <th key={col} className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#9CA3AF] min-w-[100px]">
                      {col.replace(/_/g," ")}
                    </th>
                  ))}
                  <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#7C3AED] min-w-[130px]">Theme</th>
                  <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#7C3AED] min-w-[140px]">Sub-themes</th>
                  <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#7C3AED] min-w-[100px]">Sentiment</th>
                  <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#7C3AED] min-w-[100px]">Emotion</th>
                  <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#7C3AED] min-w-[120px]">Driver</th>
                  <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#7C3AED] min-w-[100px]">Severity</th>
                  <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#7C3AED] min-w-[100px]">Confidence</th>
                  <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#7C3AED] min-w-[160px]">Signals</th>
                  <th className="px-3 py-2 text-center text-[9px] font-semibold uppercase tracking-wider text-[#7C3AED] w-16">XAI ✦</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row, i) => (
                  <tr
                    key={`row-${i}`}
                    className={`border-b border-[#F0EFE9] ${i % 2 === 0 ? "bg-white" : "bg-[#FDFCF8]"}`}
                  >
                    <td className="px-3 py-2 text-[10px] font-mono text-[#C4C2BB]">{i + 1}</td>

                    {textCol && (
                      <td className="px-3 py-2 cursor-pointer hover:bg-[#F0EBFF] transition-colors group min-w-[160px]"
                        onClick={() => openCell(textCol, row[textCol])}>
                        <p className="text-[11px] text-[#374151] truncate max-w-[200px] group-hover:text-[#7C3AED]">
                          {String(row[textCol] ?? "—")}
                        </p>
                      </td>
                    )}

                    {sourceCol && <Cell value={String(row[sourceCol] ?? "")} onClick={() => openCell(sourceCol, row[sourceCol])} />}

                    {dateCol && (
                      <td className="px-3 py-2 cursor-pointer hover:bg-[#F0EBFF] transition-colors group"
                        onClick={() => openCell(dateCol, row[dateCol])}>
                        <span className="text-[10px] text-[#9CA3AF] group-hover:text-[#7C3AED]">
                          {String(row[dateCol] ?? "—").slice(0, 19)}
                        </span>
                      </td>
                    )}

                    {extraCols.map(col => (
                      <Cell key={col} value={String(row[col] ?? "")} onClick={() => openCell(col, row[col])} />
                    ))}

                    {/* Theme */}
                    <td className="px-3 py-2 cursor-pointer hover:bg-[#F0EBFF]" onClick={() => openCell("theme", row.theme)}>
                      <span className="text-[11px] font-semibold text-[#374151] truncate max-w-[130px] block">{String(row.theme ?? "—")}</span>
                    </td>

                    {/* Sub-themes */}
                    <td className="px-3 py-2 cursor-pointer hover:bg-[#F0EBFF]"
                      onClick={() => openCell("Sub-themes", [row.sub_theme_1, row.sub_theme_2, row.sub_theme_3].filter(Boolean).join("\n"))}>
                      <div className="space-y-0.5 max-w-[140px]">
                        {[row.sub_theme_1, row.sub_theme_2, row.sub_theme_3]
                          .filter(v => Boolean(v) && String(v).trim())
                          .slice(0,2)
                          .map((v, j) => <p key={j} className="text-[10px] text-[#6B7280] truncate">{String(v)}</p>)}
                      </div>
                    </td>

                    {/* Sentiment */}
                    <td className="px-3 py-2 cursor-pointer hover:bg-[#F0EBFF]"
                      onClick={() => openCell("Sentiment", `${String(row.sentiment ?? "")}${row.sentiment_nuance ? "\n\n" + String(row.sentiment_nuance) : ""}`)}>
                      <div className="space-y-0.5">
                        <span className={`inline-block px-1.5 py-0.5 rounded-full text-[9px] font-semibold ${SENT_COLOR[String(row.sentiment)] ?? "bg-gray-100 text-gray-600"}`}>
                          {String(row.sentiment ?? "—")}
                        </span>
                        {Boolean(row.sentiment_nuance) && (
                          <p className="text-[9px] text-[#9CA3AF] truncate max-w-[100px]">{String(row.sentiment_nuance)}</p>
                        )}
                      </div>
                    </td>

                    <Cell value={String(row.emotion ?? "")} onClick={() => openCell("emotion", row.emotion)} />
                    <Cell value={String(row.driver ?? "")} onClick={() => openCell("driver", row.driver)} />

                    {/* Severity */}
                    <td className="px-3 py-2 cursor-pointer hover:bg-[#F0EBFF]"
                      onClick={() => openCell("Severity", `${String(row.severity ?? "?")}/10`)}>
                      <div className="flex items-center gap-1.5">
                        <div className="w-14 h-1.5 bg-[#E5E3DC] rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${
                            (Number(row.severity)||0) <= 3 ? "bg-emerald-500" :
                            (Number(row.severity)||0) <= 6 ? "bg-amber-500" : "bg-red-500"}`}
                            style={{ width: `${Math.min(100,(Number(row.severity)||0)/10*100)}%` }} />
                        </div>
                        <span className="text-[10px] font-mono text-[#6B7280]">{String(row.severity ?? "?")}/10</span>
                      </div>
                    </td>

                    {/* Confidence */}
                    <td className="px-3 py-2 cursor-pointer hover:bg-[#F0EBFF]"
                      onClick={() => openCell("Confidence", `${Math.round(Number(row.confidence||0)*100)}%`)}>
                      <div className="flex items-center gap-1.5">
                        <div className="w-14 h-1.5 bg-[#E5E3DC] rounded-full overflow-hidden">
                          <div className="h-full bg-[#7C3AED] rounded-full"
                            style={{ width: `${Math.round(Number(row.confidence||0)*100)}%` }} />
                        </div>
                        <span className="text-[10px] font-mono text-[#6B7280]">{Math.round(Number(row.confidence||0)*100)}%</span>
                      </div>
                    </td>

                    {/* Signals */}
                    <td className="px-3 py-2 cursor-pointer hover:bg-[#F0EBFF]"
                      onClick={() => openCell("signals", row.signals)}>
                      <div className="flex flex-wrap gap-1">
                        {String(row.signals ?? "").split(",").map(s => s.trim()).filter(Boolean).slice(0,2).map(t => (
                          <span key={t} className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${
                            /crisis|risk|backlash|misinform/i.test(t) ? "bg-red-100 text-red-600" : "bg-[#F3F2EE] text-[#6B7280]"}`}>{t}</span>
                        ))}
                        {String(row.signals ?? "").split(",").filter(s => s.trim()).length > 2 && (
                          <span className="text-[9px] text-[#9CA3AF]">+{String(row.signals).split(",").filter(s=>s.trim()).length-2}</span>
                        )}
                        {!row.signals && <span className="text-[#C4C2BB] text-[10px]">—</span>}
                      </div>
                    </td>

                    {/* XAI popup button */}
                    <td className="px-3 py-2 text-center">
                      <button
                        onClick={() => openXAI(row)}
                        className="w-7 h-7 rounded bg-[#EDE9FE] text-[#7C3AED] hover:bg-[#7C3AED] hover:text-white text-[10px] font-bold transition-colors"
                        title="View XAI Rationale"
                      >✦</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main RunHistory component ─────────────────────────────────────────────────
export default function RunHistory({ onClose }: RunHistoryProps) {
  const [runs,          setRuns]          = useState<RunMeta[]>([]);
  const [loading,       setLoading]       = useState(true);
  const [selectedId,    setSelectedId]    = useState<string | null>(null);
  const [runDetail,     setRunDetail]     = useState<RunDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    listRuns()
      .then((data: unknown) => {
        const list = Array.isArray(data) ? data : (data as { runs?: RunMeta[] })?.runs ?? [];
        setRuns(list as RunMeta[]);
      })
      .catch(() => setRuns([]))
      .finally(() => setLoading(false));
  }, []);

  async function selectRun(run_id: string) {
    if (selectedId === run_id) return;
    setSelectedId(run_id);
    setRunDetail(null);
    setLoadingDetail(true);
    try {
      const detail = await getRun(run_id);
      setRunDetail(detail as RunDetail);
    } catch {
      const stub = runs.find(r => r.run_id === run_id);
      if (stub) {
        setRunDetail({ ...stub, analyzed_data: [], columns: [] });
      } else {
        setRunDetail(null);
      }
    } finally {
      setLoadingDetail(false);
    }
  }

  function formatDate(iso: string) {
    if (!iso) return "—";
    return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  return (
    <div className="fixed inset-0 z-50 flex" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40" />
      <div
        className="relative ml-auto w-full max-w-6xl bg-[#FDFCF8] h-full flex flex-col shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#E5E3DC] shrink-0">
          <div className="flex items-center gap-2.5">
            <svg className="w-4 h-4 text-[#7C3AED]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            <span className="text-sm font-semibold text-[#1C1A16]">Run History</span>
          </div>
          <button onClick={onClose} className="text-[#9CA3AF] hover:text-[#374151] transition-colors" aria-label="Close">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar */}
          <div className="w-72 shrink-0 border-r border-[#E5E3DC] flex flex-col overflow-hidden">
            <div className="px-4 py-2.5 text-[10px] font-semibold text-[#9CA3AF] uppercase tracking-wider shrink-0">
              {loading ? "Loading…" : `${runs.length} run${runs.length !== 1 ? "s" : ""}`}
            </div>
            <div className="flex-1 overflow-y-auto">
              {loading ? (
                <div className="px-4 py-8 text-center text-xs text-[#9CA3AF]">Loading runs…</div>
              ) : runs.length === 0 ? (
                <div className="px-4 py-8 text-center text-xs text-[#9CA3AF]">No runs yet.</div>
              ) : (
                runs.map(run => (
                  <button
                    key={run.run_id}
                    onClick={() => selectRun(run.run_id)}
                    className={`w-full text-left px-4 py-3 border-b border-[#F3F2EE] hover:bg-[#F9F8F4] transition-colors
                      ${selectedId === run.run_id ? "bg-[#F3F2EE] border-l-2 border-l-[#7C3AED]" : ""}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] font-mono text-[#7C3AED] truncate max-w-[120px]">#{run.run_id.slice(0,12)}</span>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium capitalize ${STATUS_COLOR[run.status] ?? "bg-gray-100 text-gray-600"}`}>
                        {run.status}
                      </span>
                    </div>
                    <div className="text-xs font-medium text-[#1C1A16] truncate">{run.filename}</div>
                    <div className="text-[10px] text-[#9CA3AF] mt-0.5">{run.provider} · {run.completed}/{run.total_rows} rows</div>
                    <div className="text-[10px] text-[#C4C2BB]">{formatDate(run.started_at)}</div>
                  </button>
                ))
              )}
            </div>
          </div>

          {/* Main panel */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {!selectedId ? (
              <div className="flex flex-col items-center justify-center flex-1 text-center px-8">
                <svg className="w-10 h-10 text-[#E5E3DC] mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                </svg>
                <p className="text-sm text-[#9CA3AF]">Select a run to view its full results</p>
              </div>
            ) : loadingDetail ? (
              <div className="flex flex-col items-center justify-center flex-1">
                <div className="w-6 h-6 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin mb-2"/>
                <p className="text-xs text-[#9CA3AF]">Loading run data…</p>
              </div>
            ) : runDetail ? (
              <>
                {/* Run metadata bar */}
                <div className="px-5 py-2.5 border-b border-[#E5E3DC] bg-white flex items-center gap-5 flex-wrap shrink-0">
                  <div>
                    <div className="text-[9px] text-[#9CA3AF] uppercase tracking-wide">File</div>
                    <div className="text-xs font-medium text-[#1C1A16]">{runDetail.filename}</div>
                  </div>
                  <div>
                    <div className="text-[9px] text-[#9CA3AF] uppercase tracking-wide">Run ID</div>
                    <div className="text-[11px] font-mono text-[#7C3AED]">{runDetail.run_id}</div>
                  </div>
                  <div>
                    <div className="text-[9px] text-[#9CA3AF] uppercase tracking-wide">Provider</div>
                    <div className="text-xs font-medium text-[#1C1A16] capitalize">{runDetail.provider} / {runDetail.model}</div>
                  </div>
                  <div>
                    <div className="text-[9px] text-[#9CA3AF] uppercase tracking-wide">Rows</div>
                    <div className="text-xs font-medium text-[#1C1A16]">{runDetail.completed}/{runDetail.total_rows}</div>
                  </div>
                  {runDetail.elapsed_sec != null && (
                    <div>
                      <div className="text-[9px] text-[#9CA3AF] uppercase tracking-wide">Elapsed</div>
                      <div className="text-xs font-medium text-[#1C1A16]">{runDetail.elapsed_sec.toFixed(1)}s</div>
                    </div>
                  )}
                  <div>
                    <div className="text-[9px] text-[#9CA3AF] uppercase tracking-wide">Completed</div>
                    <div className="text-xs font-medium text-[#1C1A16]">{formatDate(runDetail.completed_at ?? runDetail.started_at)}</div>
                  </div>
                  <span className={`text-[9px] px-2 py-0.5 rounded-full font-medium capitalize ${STATUS_COLOR[runDetail.status] ?? "bg-gray-100 text-gray-600"}`}>
                    {runDetail.status}
                  </span>
                </div>
                <RunWorkbench run={runDetail} />
              </>
            ) : (
              <div className="flex flex-col items-center justify-center flex-1">
                <p className="text-xs text-red-500">Failed to load run data.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
