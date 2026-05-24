"use client";
import { useState } from "react";
import { setSchema, runTagging } from "../lib/api";

interface SchemaTabProps {
  sessionId: string;
  columns: string[];
  rowCount: number;
  onComplete: () => void;
}

const AI_OUTPUT_FIELDS = [
  { name: "brand",              type: "categorical",       col: 1 },
  { name: "sub_brands",         type: "list",              col: 2 },
  { name: "entities",           type: "list",              col: 1 },
  { name: "theme",              type: "categorical",       col: 2 },
  { name: "sub_theme_1",        type: "categorical",       col: 1 },
  { name: "sub_theme_2",        type: "categorical",       col: 2 },
  { name: "sub_theme_3",        type: "categorical",       col: 1 },
  { name: "sentiment",          type: "pos/neg/neu",       col: 2 },
  { name: "sentiment_nuance",   type: "categorical",       col: 2 },
  { name: "emotion",            type: "categorical",       col: 1 },
  { name: "driver",             type: "text",              col: 2 },
  { name: "severity",           type: "1-10",              col: 1 },
  { name: "signals",            type: "extracted phrases", col: 2 },
  { name: "confidence",         type: "0.0–1.0",           col: 1 },
  { name: "xai_text_evidence",  type: "text",              col: 2 },
  { name: "xai_theme_reasoning","type": "text",            col: 1 },
  { name: "xai_sentiment_reasoning","type": "text",        col: 2 },
  { name: "xai_signal_reasoning","type": "text",           col: 1 },
  { name: "xai_confidence_reasoning","type": "text",       col: 2 },
];

const PROVIDERS = [
  { id: "gemini", label: "Gemini (Google)",    envKey: "GOOGLE_API_KEY",    models: ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"] },
  { id: "groq",   label: "Groq",               envKey: "GROQ_API_KEY",      models: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"] },
  { id: "openai", label: "OpenAI",             envKey: "OPENAI_API_KEY",    models: ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"] },
  { id: "claude", label: "Claude (Anthropic)", envKey: "ANTHROPIC_API_KEY", models: ["claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022"] },
];

type UseForAI = "Yes" | "No";
interface ColConfig { show: boolean; useForAI: UseForAI; }

export default function SchemaTab({ sessionId, columns, rowCount, onComplete }: SchemaTabProps) {
  // Smart default: pick a text-like column as primary
  const defaultPrimary = columns.find(c => /detail|text|content|body|description|review/i.test(c))
    || columns[1] || columns[0] || "";

  const [primaryCol, setPrimaryCol] = useState(defaultPrimary);
  const [colConfig, setColConfig] = useState<Record<string, ColConfig>>(() => {
    const init: Record<string, ColConfig> = {};
    columns.forEach(col => { init[col] = { show: true, useForAI: "No" }; });
    if (defaultPrimary) init[defaultPrimary] = { show: true, useForAI: "Yes" };
    return init;
  });

  const [provider, setProvider]   = useState("gemini");
  const [model,    setModel]      = useState("");
  const [loading,  setLoading]    = useState(false);
  const [error,    setError]      = useState("");

  const selectedProvider = PROVIDERS.find(p => p.id === provider)!;
  const visibleCount = columns.filter(c => colConfig[c]?.show).length;
  const aiCount      = columns.filter(c => colConfig[c]?.useForAI === "Yes").length;

  const handlePrimaryChange = (col: string) => {
    setPrimaryCol(col);
    setColConfig(prev => ({ ...prev, [col]: { ...prev[col], show: true, useForAI: "Yes" } }));
  };

  const toggleShow = (col: string) =>
    setColConfig(prev => ({ ...prev, [col]: { ...prev[col], show: !prev[col]?.show } }));

  const setAI = (col: string, val: UseForAI) =>
    setColConfig(prev => ({ ...prev, [col]: { ...prev[col], useForAI: val } }));

  const handleRun = async () => {
    if (!primaryCol) { setError("Please select a primary text column"); return; }
    setError("");
    setLoading(true);
    try {
      const visibleCols = columns.filter(c => colConfig[c]?.show);
      const aiCols      = columns.filter(c => colConfig[c]?.useForAI === "Yes");
      await setSchema({ session_id: sessionId, primary_text_column: primaryCol, visible_columns: visibleCols, ai_columns: aiCols });
      await runTagging({ session_id: sessionId, provider, model: model || undefined });
      onComplete();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start tagging");
      setLoading(false);
    }
  };

  const leftFields  = AI_OUTPUT_FIELDS.filter(f => f.col === 1);
  const rightFields = AI_OUTPUT_FIELDS.filter(f => f.col === 2);

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-5">

      {/* Header */}
      <div>
        <p className="text-[10px] font-semibold tracking-[0.15em] text-[#9CA3AF] uppercase mb-1">Step 2 of 3 · Required</p>
        <h1 className="text-[22px] font-bold text-[#111827]">Configure <span className="text-[#7C3AED]">tagging schema</span></h1>
        <p className="text-[13px] text-[#6B7280] mt-1">Pick which column the AI should read. Map at least one to Original Text to continue.</p>
      </div>

      {/* Auto-fill banner */}
      <div className="flex items-center justify-between bg-[#EDE9FE] border border-[#C4B5FD] rounded-xl px-4 py-2.5">
        <div>
          <p className="text-[12px] font-semibold text-[#5B21B6]">Auto-fill missing fields with AI</p>
          <p className="text-[11px] text-[#7C3AED]/70">Infer brand, rating, and Author from text if a source-column isn&apos;t present.</p>
        </div>
        <div className="w-9 h-5 bg-[#7C3AED] rounded-full relative flex-shrink-0">
          <div className="w-3.5 h-3.5 bg-white rounded-full absolute right-0.5 top-0.5 shadow-sm" />
        </div>
      </div>

      {/* Primary text column */}
      <div className="bg-white border border-[#E5E3DC] rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-[#E5E3DC] bg-[#FDFCF8]">
          <p className="text-[10px] font-semibold text-[#374151] uppercase tracking-wider">Primary Text Column — Required</p>
          <p className="text-[11px] text-[#9CA3AF] mt-0.5">Which column contains the text to analyze? The AI reads this for theme, sentiment, emotion, and signal extraction.</p>
        </div>
        <div className="px-4 py-3">
          <select value={primaryCol} onChange={e => handlePrimaryChange(e.target.value)}
            className="px-2.5 py-1.5 text-[12px] border border-[#E5E3DC] rounded-lg bg-white focus:outline-none focus:border-[#7C3AED] text-[#374151] font-medium">
            {columns.map(col => <option key={col} value={col}>{col}</option>)}
          </select>
          {primaryCol && (
            <span className="ml-3 text-[11px] text-[#7C3AED] bg-[#EDE9FE] px-2 py-0.5 rounded">
              ✓ {primaryCol} selected as primary text
            </span>
          )}
        </div>
      </div>

      {/* Column table */}
      <div className="bg-white border border-[#E5E3DC] rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#E5E3DC] bg-[#FDFCF8]">
          <p className="text-[11px] font-semibold text-[#374151]">
            Your Columns
            <span className="text-[#9CA3AF] font-normal ml-1.5">
              · {columns.length} detected · {visibleCount} visible · {aiCount} used for AI
            </span>
          </p>
          <div className="flex items-center gap-3">
            <button onClick={() => columns.forEach(c => setColConfig(prev => ({ ...prev, [c]: { ...prev[c], show: true } })))}
              className="text-[11px] text-[#7C3AED] hover:underline">Include all</button>
            <button onClick={() => columns.forEach(c => setColConfig(prev => ({ ...prev, [c]: { ...prev[c], show: false } })))}
              className="text-[11px] text-[#9CA3AF] hover:underline">Clear</button>
          </div>
        </div>

        <table className="w-full">
          <thead>
            <tr className="border-b border-[#E5E3DC] bg-[#F8F7F3]">
              <th className="w-10 px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-[#9CA3AF] text-left">Show</th>
              <th className="px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-[#9CA3AF] text-left">Column</th>
              <th className="px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-[#9CA3AF] text-left w-36">Use for AI</th>
              <th className="px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-[#9CA3AF] text-left">Sample Data</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((col, i) => {
              const cfg = colConfig[col] ?? { show: true, useForAI: "No" };
              return (
                <tr key={col} className={`border-b border-[#F0EFE9] last:border-0 ${i % 2 === 0 ? "bg-white" : "bg-[#FDFCF8]"}`}>
                  <td className="px-4 py-2.5">
                    <input type="checkbox" checked={cfg.show} onChange={() => toggleShow(col)}
                      className="rounded border-[#D1D0CC] accent-[#7C3AED] w-3.5 h-3.5" />
                  </td>
                  <td className="px-4 py-2.5 text-[12px] font-medium text-[#374151]">
                    {col}
                    {col === primaryCol && (
                      <span className="ml-2 text-[9px] font-bold text-[#7C3AED] bg-[#EDE9FE] px-1.5 py-0.5 rounded uppercase tracking-wider">Primary Text</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <select value={cfg.useForAI} onChange={e => setAI(col, e.target.value as UseForAI)}
                      className="px-2 py-1 text-[11px] border border-[#E5E3DC] rounded bg-white focus:outline-none focus:border-[#7C3AED] text-[#374151]">
                      <option>Yes</option>
                      <option>No</option>
                    </select>
                  </td>
                  <td className="px-4 py-2.5 text-[11px] text-[#9CA3AF] italic max-w-[260px] truncate">—</td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {/* Stats footer */}
        <div className="border-t border-[#E5E3DC] px-4 py-2.5 flex items-center gap-8 bg-[#FDFCF8]">
          <div className="text-[11px]"><span className="font-semibold text-amber-600">{rowCount}</span> <span className="text-[#9CA3AF]">Total Rows</span></div>
          <div className="text-[11px]"><span className="font-semibold text-[#374151]">{visibleCount} / {columns.length}</span> <span className="text-[#9CA3AF]">Visible Columns</span></div>
          <div className="text-[11px]"><span className="font-semibold text-[#374151]">{aiCount} / {columns.length}</span> <span className="text-[#9CA3AF]">Used for AI</span></div>
          <div className="text-[11px]"><span className="font-semibold text-[#7C3AED]">16</span> <span className="text-[#9CA3AF]">AI Outputs</span></div>
        </div>
      </div>

      {/* AI Output fields */}
      <div className="bg-white border border-[#E5E3DC] rounded-xl overflow-hidden">
        <div className="px-4 py-2.5 bg-[#FDFCF8] border-b border-[#E5E3DC]">
          <p className="text-[11px] font-semibold text-[#7C3AED] uppercase tracking-wider">✦ AI Will Add These Columns</p>
          <p className="text-[10px] text-[#9CA3AF]">appended to every row</p>
        </div>
        <div className="px-4 py-3 grid grid-cols-2 gap-x-8 gap-y-2">
          {leftFields.map((f, i) => (
            <div key={f.name} className="contents">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[#7C3AED] flex-shrink-0" />
                <span className="text-[11px] font-mono font-medium text-[#374151]">{f.name}</span>
                <span className="text-[10px] text-[#9CA3AF] bg-[#F3F2EE] px-1.5 py-0.5 rounded ml-auto">{f.type}</span>
              </div>
              {rightFields[i] && (
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#7C3AED] flex-shrink-0" />
                  <span className="text-[11px] font-mono font-medium text-[#374151]">{rightFields[i].name}</span>
                  <span className="text-[10px] text-[#9CA3AF] bg-[#F3F2EE] px-1.5 py-0.5 rounded ml-auto">{rightFields[i].type}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* LLM config — NO API KEY FIELD (reads from backend .env) */}
      <div className="bg-white border border-[#E5E3DC] rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-[10px] font-semibold text-[#374151] uppercase tracking-wider">AI Engine</p>
          <div className="flex items-center gap-1.5 text-[10px] text-[#9CA3AF]">
            <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" />
            API keys loaded from server .env
          </div>
        </div>
        <div className="flex gap-3">
          <div className="min-w-[160px]">
            <label className="text-[10px] text-[#9CA3AF] block mb-1">Provider</label>
            <select value={provider} onChange={e => { setProvider(e.target.value); setModel(""); }}
              className="w-full px-2.5 py-1.5 text-[12px] border border-[#E5E3DC] rounded-lg bg-white focus:outline-none focus:border-[#7C3AED] text-[#374151]">
              {PROVIDERS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
          </div>
          <div className="min-w-[220px]">
            <label className="text-[10px] text-[#9CA3AF] block mb-1">Model</label>
            <select value={model} onChange={e => setModel(e.target.value)}
              className="w-full px-2.5 py-1.5 text-[12px] border border-[#E5E3DC] rounded-lg bg-white focus:outline-none focus:border-[#7C3AED] text-[#374151]">
              <option value="">Default ({selectedProvider.models[0]})</option>
              {selectedProvider.models.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div className="flex-1 flex items-end">
            <p className="text-[11px] text-[#9CA3AF] pb-1.5">
              Configure keys in <span className="font-mono bg-[#F3F2EE] px-1 rounded">backend/.env</span>
            </p>
          </div>
        </div>
      </div>

      {error && <p className="text-[12px] text-red-600 bg-red-50 border border-red-200 px-3 py-2 rounded-lg">{error}</p>}

      {/* Footer */}
      <div className="flex items-center justify-between pt-1">
        <span className="text-[11px] text-[#9CA3AF]">
          Processing: {rowCount} rows in batches of 5 with 3 concurrent workers
        </span>
        <button
          onClick={handleRun}
          disabled={loading || !primaryCol}
          className="flex items-center gap-2 px-4 py-2 bg-[#7C3AED] hover:bg-[#6D28D9] disabled:bg-[#C4B5FD] disabled:cursor-not-allowed text-white text-[12px] font-semibold rounded-lg transition-colors shadow-sm"
        >
          {loading ? (
            <><div className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />Starting…</>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Run AI tagging · {rowCount} rows
            </>
          )}
        </button>
      </div>
    </div>
  );
}
