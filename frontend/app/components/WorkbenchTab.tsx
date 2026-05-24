import { useEffect, useState, useCallback } from "react";
import { getStatus, getResults, exportUrl, updateRow } from "../lib/api";

interface WorkbenchTabProps {
  sessionId: string;
  rowCount: number;
  onGoExport: () => void;
}

// ── AI field registry ─────────────────────────────────────────────────────────
const AI_KEYS = new Set([
  "brand", "sub_brands", "entities", "theme","sub_theme_1","sub_theme_2","sub_theme_3",
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
  | { type: "cell"; col: string; value: string; rowIdx: number }
  | { type: "xai";  row: Record<string, unknown> };

// ── Unified popup modal ───────────────────────────────────────────────────────
function Popup({ state, sessionId, onClose, onSave }: { state: PopupState; sessionId: string; onClose: () => void; onSave: (col: string, val: string, idx: number) => void }) {
  const [editVal, setEditVal] = useState(state.type === "cell" ? state.value : "");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (state.type !== "cell") return;
    setSaving(true);
    try {
      await updateRow(sessionId, state.rowIdx, state.col, editVal);
      onSave(state.col, editVal, state.rowIdx);
      onClose();
    } catch (e) {
      console.error(e);
      alert("Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/40" />
      <div
        className="relative bg-white/95 backdrop-blur-md rounded-2xl shadow-[0_20px_50px_rgba(8,_112,_184,_0.1)] w-full max-w-xl flex flex-col overflow-hidden border border-white/40 ring-1 ring-black/5"
        style={{ maxHeight: "80vh" }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 shrink-0 bg-white/50">
          {state.type === "cell" ? (
            <span className="text-[11px] font-bold text-[#7C3AED] uppercase tracking-widest bg-purple-50 px-3 py-1.5 rounded-full border border-purple-100">
              Edit: {state.col.replace(/_/g, " ")}
            </span>
          ) : (
            <div className="flex items-center gap-3">
              <span className="text-[11px] font-bold text-white uppercase tracking-widest bg-gradient-to-r from-[#7C3AED] to-[#DB2777] px-3 py-1.5 rounded-full shadow-md">
                ✦ Explainable AI Rationale
              </span>
              <span className="text-[10px] text-gray-400 font-medium tracking-wide">100% Grounded</span>
            </div>
          )}
          <button
            onClick={onClose}
            className="ml-3 shrink-0 w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-all"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div className="overflow-y-auto flex-1 px-6 py-5 scrollbar-thin scrollbar-thumb-gray-200">
          {state.type === "cell" ? (
            <div className="flex flex-col gap-4">
              <textarea 
                value={editVal}
                onChange={e => setEditVal(e.target.value)}
                className="w-full h-32 p-4 text-[13px] text-gray-800 border border-gray-200 rounded-xl focus:ring-2 focus:ring-[#7C3AED]/20 focus:border-[#7C3AED] outline-none resize-none transition-all shadow-inner bg-gray-50/50"
              />
              <div className="flex justify-end gap-3 mt-1">
                <button onClick={onClose} className="px-5 py-2 text-[12px] font-medium text-gray-500 hover:bg-gray-100 rounded-xl transition-colors">Cancel</button>
                <button onClick={handleSave} disabled={saving} className="px-5 py-2 text-[12px] font-medium text-white bg-gradient-to-r from-[#7C3AED] to-[#6D28D9] hover:shadow-lg hover:shadow-purple-500/20 rounded-xl transition-all disabled:opacity-50 flex items-center gap-2">
                  {saving && <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/></svg>}
                  {saving ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </div>
          ) : (
            <XAIContent row={state.row} />
          )}
        </div>
      </div>
    </div>
  );
}

// ── XAI content (used inside popup) ──────────────────────────────────────────
function XAIContent({ row }: { row: Record<string, unknown> }) {
  return (
    <div className="space-y-4">
      {Boolean(row.xai_text_evidence) && (
        <div className="bg-gradient-to-br from-[#F9F8FF] to-white border border-[#E9E4FF] rounded-xl p-5 shadow-sm relative overflow-hidden group">
          <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-[#7C3AED] to-[#DB2777]" />
          <p className="text-[10px] font-bold text-transparent bg-clip-text bg-gradient-to-r from-[#7C3AED] to-[#DB2777] uppercase tracking-widest mb-3 flex items-center gap-1.5">
            <svg className="w-3.5 h-3.5 text-[#7C3AED]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/></svg>
            Verbatim Evidence
          </p>
          <blockquote className="text-[13px] text-gray-700 italic leading-relaxed relative z-10 pl-2">
            &ldquo;{String(row.xai_text_evidence)}&rdquo;
          </blockquote>
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {([
        ["xai_theme_reasoning",     "🏷",  "Theme",      "from-purple-50 to-white", "border-purple-100", "text-purple-700"],
        ["xai_sentiment_reasoning", "💬",  "Sentiment",  "from-emerald-50 to-white", "border-emerald-100", "text-emerald-700"],
        ["xai_signal_reasoning",    "⚡",  "Signals",     "from-amber-50 to-white", "border-amber-100", "text-amber-700"],
        ["xai_confidence_reasoning","📊",  "Confidence", "from-sky-50 to-white", "border-sky-100", "text-sky-700"],
      ] as [string, string, string, string, string, string][]).map(([key, icon, label, bg, border, color]) =>
        Boolean(row[key]) ? (
          <div key={key} className={`bg-gradient-to-br ${bg} border ${border} rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow duration-300`}>
            <p className={`text-[10px] font-bold uppercase tracking-widest mb-2 flex items-center gap-1.5 ${color}`}>
              <span className="text-[14px]">{icon}</span> {label}
            </p>
            <p className="text-[12px] text-gray-600 leading-relaxed">{String(row[key])}</p>
          </div>
        ) : null
      )}
      </div>
    </div>
  );
}

// ── Reusable cell ─────────────────────────────────────────────────────────────
function Cell({ value, onClick }: { value: string; onClick: () => void }) {
  return (
    <td
      className="px-3 py-2 cursor-pointer hover:bg-[#F0EBFF] transition-colors group"
      onClick={onClick}
    >
      <span className="block truncate max-w-[140px] text-[11px] text-[#374151] group-hover:text-[#7C3AED]">
        {value || <span className="text-[#D1D0CC]">—</span>}
      </span>
    </td>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function WorkbenchTab({ sessionId, rowCount, onGoExport }: WorkbenchTabProps) {
  const [status,       setStatus]       = useState("running");
  const [progress,     setProgress]     = useState(0);
  const [analyzedRows, setAnalyzedRows] = useState(0);
  const [data,         setData]         = useState<Record<string, unknown>[]>([]);
  const [filterSent,   setFilterSent]   = useState("All sentiments");
  const [filterTheme,  setFilterTheme]  = useState("All themes");
  const [search,       setSearch]       = useState("");
  const [errorMsg,     setErrorMsg]     = useState("");
  const [popup,        setPopup]        = useState<PopupState | null>(null);

  const poll = useCallback(async () => {
    try {
      const st = await getStatus(sessionId);
      setStatus(st.status ?? "unknown");
      setProgress(st.progress ?? 0);
      setAnalyzedRows(st.analyzed_rows ?? 0);
      if ((st.analyzed_rows ?? 0) > 0) {
        const res = await getResults(sessionId);
        setData(res.analyzed_data ?? []);
      }
      if (st.error_message) setErrorMsg(st.error_message);
    } catch (e) {
      console.error("[WorkbenchTab] poll error", e);
    }
  }, [sessionId]);

  useEffect(() => { poll(); }, [poll]);

  useEffect(() => {
    if (status === "complete" || status === "error") return;
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, [poll, status]);

  const origCols     = data.length ? Object.keys(data[0]).filter(k => !AI_KEYS.has(k)) : [];
  const textCol      = origCols.find(k => /detail|text|content|body|description|review|title/i.test(k)) ?? origCols[0];
  const sourceCol    = origCols.find(k => /source|platform|channel|media.?type/i.test(k));
  const dateCol      = origCols.find(k => /date|time|publish/i.test(k));
  const extraOrigCols = origCols.filter(k => k !== textCol && k !== sourceCol && k !== dateCol);

  const themes = Array.from(new Set(data.map(r => String(r.theme ?? "")).filter(Boolean)));

  const filtered = data.filter(row => {
    if (filterSent  !== "All sentiments" && String(row.sentiment) !== filterSent)  return false;
    if (filterTheme !== "All themes"     && String(row.theme)     !== filterTheme) return false;
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

  const openCell = (col: string, value: unknown, rowIdx: number) =>
    setPopup({ type: "cell", col, value: String(value ?? ""), rowIdx });
  const openXAI = (row: Record<string, unknown>) =>
    setPopup({ type: "xai", row });

  const handleSaveCell = (col: string, val: string, idx: number) => {
    setData(prev => {
      const copy = [...prev];
      copy[idx] = { ...copy[idx], [col]: val };
      return copy;
    });
  };

  return (
    <div className="flex flex-col h-full bg-[#FDFCF8]">

      {/* Popup */}
      {popup && <Popup state={popup} sessionId={sessionId} onClose={() => setPopup(null)} onSave={handleSaveCell} />}

      {/* Stats header */}
      <div className="bg-white border-b border-[#E5E3DC] px-5 py-2 shrink-0">
        <div className="flex items-center gap-5 flex-wrap">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded bg-[#7C3AED] flex items-center justify-center">
              <svg className="w-2.5 h-2.5 text-white" fill="currentColor" viewBox="0 0 12 12"><circle cx="6" cy="6" r="4" /></svg>
            </div>
            <div className="leading-none">
              <p className="text-[9px] font-bold text-[#7C3AED] uppercase tracking-widest">E-AI Intelligence</p>
              <p className="text-[9px] text-[#9CA3AF]">Active dataset</p>
            </div>
          </div>
          <div className="w-px h-5 bg-[#E5E3DC]" />
          {([
            ["Total",    String(total),                                    "text-[#111827]"],
            ["Positive", `${total ? Math.round(positive/total*100) : 0}%`, "text-emerald-600"],
            ["Negative", `${total ? Math.round(negative/total*100) : 0}%`, "text-red-500"],
            ["Avg Conf", `${avgConf}%`,                                    "text-[#7C3AED]"],
          ] as [string, string, string][]).map(([label, value, color]) => (
            <div key={label} className="text-center">
              <p className={`text-[15px] font-bold leading-none ${color}`}>{value}</p>
              <p className="text-[9px] text-[#9CA3AF] mt-0.5 uppercase tracking-wider">{label}</p>
            </div>
          ))}
          <div className="ml-auto flex items-center gap-1.5">
            <button onClick={onGoExport} className="flex items-center gap-1 text-[10px] text-white bg-[#7C3AED] hover:bg-[#6D28D9] px-2.5 py-1 rounded font-medium">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
              </svg>
              Export
            </button>
            <a href={exportUrl(sessionId,"csv")}  download className="text-[10px] text-[#6B7280] hover:text-[#374151] px-2 py-1 border border-[#E5E3DC] rounded bg-white">CSV</a>
            <a href={exportUrl(sessionId,"xlsx")} download className="text-[10px] text-[#6B7280] hover:text-[#374151] px-2 py-1 border border-[#E5E3DC] rounded bg-white">XLSX</a>
          </div>
        </div>
      </div>

      {/* Filter toolbar */}
      <div className="bg-white border-b border-[#E5E3DC] px-5 py-2 flex items-center gap-2 flex-wrap shrink-0">
        <div className="relative">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-[#9CA3AF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          <input type="text" value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search text, theme, signal…"
            className="pl-7 pr-3 py-1.5 text-[11px] border border-[#E5E3DC] rounded-lg bg-white focus:outline-none focus:border-[#7C3AED] w-52 placeholder:text-[#C4C2BB]"/>
        </div>
        <select value={filterSent} onChange={e => setFilterSent(e.target.value)}
          className="px-2.5 py-1.5 text-[11px] border border-[#E5E3DC] rounded-lg bg-white focus:outline-none focus:border-[#7C3AED] text-[#374151]">
          {["All sentiments","Positive","Negative","Neutral","Mixed"].map(s => <option key={s}>{s}</option>)}
        </select>
        <select value={filterTheme} onChange={e => setFilterTheme(e.target.value)}
          className="px-2.5 py-1.5 text-[11px] border border-[#E5E3DC] rounded-lg bg-white focus:outline-none focus:border-[#7C3AED] text-[#374151]">
          <option value="All themes">All themes ({themes.length})</option>
          {themes.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <div className="ml-auto text-[10px] text-[#9CA3AF]">{filtered.length} / {total} rows</div>
      </div>

      {/* Progress / error bar */}
      {status === "running" && (
        <div className="bg-[#EDE9FE] border-b border-[#C4B5FD] px-5 py-1.5 flex items-center gap-3 shrink-0">
          <div className="flex-1 h-1.5 bg-[#C4B5FD] rounded-full overflow-hidden">
            <div className="h-full bg-[#7C3AED] transition-all duration-500 rounded-full" style={{ width: `${progress}%` }} />
          </div>
          <span className="text-[10px] text-[#7C3AED] font-medium whitespace-nowrap">
            {analyzedRows} / {rowCount} rows · {progress}%
          </span>
        </div>
      )}
      {status === "error" && (
        <div className="bg-red-50 border-b border-red-200 px-5 py-2 text-[11px] text-red-600 shrink-0">
          ⚠ Analysis failed: {errorMsg || "Check your API key in backend/.env and restart."}
        </div>
      )}

      {/* Loading spinner */}
      {data.length === 0 && status === "running" && (
        <div className="flex-1 flex flex-col items-center justify-center">
          <div className="w-9 h-9 border-[3px] border-[#7C3AED] border-t-transparent rounded-full animate-spin mb-4" />
          <p className="text-[13px] font-medium text-[#374151]">AI analysis in progress…</p>
          <p className="text-[11px] text-[#9CA3AF] mt-1">{rowCount} rows · {progress}% complete</p>
        </div>
      )}

      {/* Data grid */}
      {filtered.length > 0 && (
        <div className="flex-1 overflow-auto px-5 py-3">
          <div className="text-[10px] text-[#9CA3AF] mb-2">
            Click any cell to view full content · Click <span className="text-[#7C3AED] font-medium">✦</span> to view XAI rationale · Scroll right →
          </div>
          <div className="border border-[#E5E3DC] rounded-xl bg-white" style={{ overflowX: "auto" }}>
            <table className="text-[11px] border-collapse" style={{ minWidth: "max-content", width: "100%" }}>
              <thead>
                <tr className="bg-[#F8F7F3] border-b border-[#E5E3DC]">
                  <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#9CA3AF] w-8">#</th>

                  {textCol && (
                    <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#9CA3AF] min-w-[180px]">
                      {textCol.replace(/_/g," ")}
                    </th>
                  )}
                  {sourceCol && (
                    <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#9CA3AF] min-w-[100px]">
                      {sourceCol.replace(/_/g," ")}
                    </th>
                  )}
                  {dateCol && (
                    <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#9CA3AF] min-w-[90px]">
                      {dateCol.replace(/_/g," ")}
                    </th>
                  )}
                  {extraOrigCols.map(col => (
                    <th key={col} className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#9CA3AF] min-w-[100px]">
                      {col.replace(/_/g," ")}
                    </th>
                  ))}

                  {/* AI columns — purple headers */}
                  <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#7C3AED] min-w-[100px]">Brand</th>
                  <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#7C3AED] min-w-[120px]">Sub-brands</th>
                  <th className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-wider text-[#7C3AED] min-w-[120px]">Entities</th>
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
                      <td className="px-3 py-2 cursor-pointer hover:bg-[#F0EBFF] transition-colors group min-w-[180px]"
                        onClick={() => openCell(textCol, row[textCol], i)}>
                        <p className="text-[11px] text-[#374151] truncate max-w-[200px] group-hover:text-[#7C3AED]">
                          {String(row[textCol] ?? "—")}
                        </p>
                      </td>
                    )}

                    {sourceCol && (
                      <Cell value={String(row[sourceCol] ?? "")} onClick={() => openCell(sourceCol, row[sourceCol], i)} />
                    )}

                    {dateCol && (
                      <td className="px-3 py-2 cursor-pointer hover:bg-[#F0EBFF] transition-colors group"
                        onClick={() => openCell(dateCol, row[dateCol], i)}>
                        <span className="text-[10px] text-[#9CA3AF] group-hover:text-[#7C3AED]">
                          {String(row[dateCol] ?? "—").slice(0, 19)}
                        </span>
                      </td>
                    )}

                    {extraOrigCols.map(col => (
                      <Cell key={col} value={String(row[col] ?? "")} onClick={() => openCell(col, row[col], i)} />
                    ))}

                    {/* Brand */}
                    <Cell value={String(row.brand ?? "")} onClick={() => openCell("brand", row.brand, i)} />

                    {/* Sub Brands */}
                    <Cell value={Array.isArray(row.sub_brands) ? row.sub_brands.join(", ") : String(row.sub_brands ?? "")} onClick={() => openCell("sub_brands", Array.isArray(row.sub_brands) ? row.sub_brands.join(", ") : String(row.sub_brands ?? ""), i)} />

                    {/* Entities */}
                    <Cell value={Array.isArray(row.entities) ? row.entities.join(", ") : String(row.entities ?? "")} onClick={() => openCell("entities", Array.isArray(row.entities) ? row.entities.join(", ") : String(row.entities ?? ""), i)} />

                    {/* Theme */}
                    <td className="px-3 py-2 cursor-pointer hover:bg-[#F0EBFF]" onClick={() => openCell("theme", row.theme, i)}>
                      <span className="text-[11px] font-semibold text-[#374151] truncate max-w-[130px] block">{String(row.theme ?? "—")}</span>
                    </td>

                    {/* Sub-themes */}
                    <td className="px-3 py-2 cursor-pointer hover:bg-[#F0EBFF]"
                      onClick={() => openCell("sub_theme_1", [row.sub_theme_1, row.sub_theme_2, row.sub_theme_3].filter(Boolean).join("\n"), i)}>
                      <div className="space-y-0.5 max-w-[140px]">
                        {[row.sub_theme_1, row.sub_theme_2, row.sub_theme_3]
                          .filter(v => Boolean(v) && String(v).trim())
                          .slice(0, 2)
                          .map((v, j) => (
                            <p key={j} className="text-[10px] text-[#6B7280] truncate">{String(v)}</p>
                          ))}
                      </div>
                    </td>

                    {/* Sentiment */}
                    <td className="px-3 py-2 cursor-pointer hover:bg-[#F0EBFF]"
                      onClick={() => openCell("sentiment", `${String(row.sentiment ?? "")}${row.sentiment_nuance ? "\n\n" + String(row.sentiment_nuance) : ""}`, i)}>
                      <div className="space-y-0.5">
                        <span className={`inline-block px-1.5 py-0.5 rounded-full text-[9px] font-semibold ${SENT_COLOR[String(row.sentiment)] ?? "bg-gray-100 text-gray-600"}`}>
                          {String(row.sentiment ?? "—")}
                        </span>
                        {Boolean(row.sentiment_nuance) && (
                          <p className="text-[9px] text-[#9CA3AF] truncate max-w-[100px]">{String(row.sentiment_nuance)}</p>
                        )}
                      </div>
                    </td>

                    {/* Emotion */}
                    <Cell value={String(row.emotion ?? "")} onClick={() => openCell("emotion", row.emotion, i)} />

                    {/* Driver */}
                    <Cell value={String(row.driver ?? "")} onClick={() => openCell("driver", row.driver, i)} />

                    {/* Severity */}
                    <td className="px-3 py-2 cursor-pointer hover:bg-[#F0EBFF]"
                      onClick={() => openCell("severity", `${String(row.severity ?? "?")}`, i)}>
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
                      onClick={() => openCell("confidence", `${Math.round(Number(row.confidence||0)*100)}`, i)}>
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
                      onClick={() => openCell("signals", row.signals, i)}>
                      <div className="flex flex-wrap gap-1">
                        {String(row.signals ?? "").split(",").map(s => s.trim()).filter(Boolean).slice(0,2).map(t => (
                          <span key={t} className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${
                            /crisis|risk|backlash|misinform/i.test(t) ? "bg-red-100 text-red-600" : "bg-[#F3F2EE] text-[#6B7280]"}`}>
                            {t}
                          </span>
                        ))}
                        {String(row.signals ?? "").split(",").filter(s => s.trim()).length > 2 && (
                          <span className="text-[9px] text-[#9CA3AF]">+{String(row.signals).split(",").filter(s=>s.trim()).length - 2}</span>
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
      )}
    </div>
  );
}
