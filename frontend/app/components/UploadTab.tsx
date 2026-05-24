"use client";
import { useCallback, useState } from "react";
import { uploadFile, setContext } from "../lib/api";

interface UploadTabProps {
  onComplete: (data: {
    sessionId: string;
    filename: string;
    columns: string[];
    rowCount: number;
    preview: Record<string, unknown>[];
  }) => void;
}

const DATASET_TYPES = [
  { id: "Single brand", label: "Single brand", sub: "All rows are about one brand" },
  { id: "Industry / category", label: "Industry / category", sub: "Multi-brand active one industry" },
  { id: "Mixed / unknown", label: "Mixed / unknown", sub: "Let AI figure out everything" },
];

const QUICK_PROMPTS = [
  "B2C reviews",
  "Social media posts",
  "News articles",
  "Survey responses",
  "Customer support tickets",
  "Pharma vigilance",
];

export default function UploadTab({ onComplete }: UploadTabProps) {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Record<string, unknown>[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [rowCount, setRowCount] = useState(0);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const [datasetType, setDatasetType] = useState("Single brand");
  const [focusBrand, setFocusBrand] = useState("");
  const [additionalContext, setAdditionalContext] = useState("");

  const handleFile = useCallback(async (f: File) => {
    setFile(f);
    setError("");
    setUploading(true);
    try {
      const res = await uploadFile(f);
      setPreview(res.preview);
      setColumns(res.columns);
      setRowCount(res.row_count);
      setSessionId(res.session_id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, [handleFile]);

  const handleInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFile(f);
  };

  const handleContinue = async () => {
    if (!sessionId) return;
    try {
      await setContext({
        session_id: sessionId,
        dataset_type: datasetType,
        focus_brand: focusBrand,
        additional_context: additionalContext,
      });
      onComplete({ sessionId, filename: file!.name, columns, rowCount, preview });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save context");
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-5">

      {/* ── Header ─────────────────────────────────────────────────── */}
      <div>
        <p className="text-[10px] font-semibold tracking-[0.15em] text-[#9CA3AF] uppercase mb-1">
          Step 1 of 3 · Required
        </p>
        <h1 className="text-[22px] font-bold text-[#111827] leading-tight">
          Upload <span className="text-[#7C3AED]">your dataset</span>
        </h1>
        <p className="text-[13px] text-[#6B7280] mt-1">
          Drop one or more files below — Excel, CSV, JSON, or Word. We&apos;ll parse them in the browser
          and auto-detect the schema on the next step.
        </p>
      </div>

      {/* ── Drop zone ──────────────────────────────────────────────── */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => document.getElementById("fu-input")?.click()}
        className={`relative flex flex-col items-center justify-center gap-3 py-10 rounded-xl border-2 border-dashed cursor-pointer transition-all
          ${dragging ? "border-[#7C3AED] bg-[#F5F3FF]" : "border-[#D1CFCA] bg-white hover:border-[#A78BFA] hover:bg-[#FDFBFF]"}`}
      >
        <input id="fu-input" type="file" className="hidden" accept=".csv,.xlsx,.xls,.json,.docx" onChange={handleInput} />

        {/* Upload icon */}
        <div className="w-11 h-11 rounded-full bg-[#F3F2EE] flex items-center justify-center">
          {uploading
            ? <div className="w-5 h-5 border-2 border-[#7C3AED] border-t-transparent rounded-full animate-spin" />
            : <svg className="w-5 h-5 text-[#9CA3AF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
              </svg>
          }
        </div>

        <div className="text-center">
          <p className="text-[13px] font-medium text-[#374151]">
            {uploading ? "Uploading…" : "Drop one or more files to click to browse"}
          </p>
          <p className="text-[11px] text-[#9CA3AF] mt-0.5">parsed locally in your browser</p>
        </div>

        {/* Format badges */}
        <div className="flex items-center gap-1.5">
          {["xlsx", "csv", "json", "docx"].map(f => (
            <span key={f} className="text-[10px] font-semibold uppercase px-2 py-0.5 bg-[#F3F2EE] rounded text-[#6B7280] tracking-wide">
              {f}
            </span>
          ))}
        </div>
      </div>

      {error && (
        <div className="text-[12px] text-red-600 bg-red-50 border border-red-200 px-3 py-2 rounded-lg">{error}</div>
      )}

      {/* ── Uploaded file card ─────────────────────────────────────── */}
      {file && columns.length > 0 && (
        <div className="border border-[#E5E3DC] rounded-xl overflow-hidden bg-white">

          {/* File header row */}
          <div className="flex items-center gap-2 px-4 py-2.5 bg-[#FDFCF8] border-b border-[#E5E3DC]">
            <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-[#EDE9FE] text-[#7C3AED]">
              {file.name.split(".").pop()?.toUpperCase()}
            </span>
            <span className="text-[12px] font-semibold text-[#374151] truncate flex-1">{file.name}</span>
            <span className="text-[11px] text-[#9CA3AF] whitespace-nowrap">
              {(file.size / 1024).toFixed(0)} KB · {rowCount} rows × {columns.length} cols
            </span>
            <button
              onClick={e => { e.stopPropagation(); setFile(null); setPreview([]); setColumns([]); setSessionId(null); }}
              className="ml-1 text-[#9CA3AF] hover:text-[#6B7280] text-base leading-none"
            >×</button>
          </div>

          {/* Preview label */}
          <div className="flex items-center justify-between px-4 py-1.5 border-b border-[#EDEBE4] bg-[#FAFAF7]">
            <span className="text-[11px] text-[#6B7280]">
              ↳ Preview — first 4 of {rowCount} rows
            </span>
            <span className="text-[11px] text-[#9CA3AF]">{columns.length} columns</span>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-[#F8F7F3] border-b border-[#E5E3DC]">
                  {columns.map(col => (
                    <th key={col} className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-[#9CA3AF] whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.map((row, i) => (
                  <tr key={i} className="border-b border-[#F0EFE9] last:border-0">
                    {columns.map(col => (
                      <td key={col} className="px-3 py-2 text-[11px] text-[#374151] max-w-[200px] truncate">
                        {String(row[col] ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Dataset context (shown after upload) ──────────────────── */}
      {sessionId && (
        <div className="border border-[#E5E3DC] rounded-xl overflow-hidden bg-white">

          {/* Section header */}
          <div className="px-4 py-2.5 bg-[#FDFCF8] border-b border-[#E5E3DC]">
            <p className="text-[11px] font-semibold text-[#374151] uppercase tracking-wider">Dataset context</p>
            <p className="text-[11px] text-[#9CA3AF]">Optional — a few words meaningfully sharpens the AI&apos;s tagging</p>
          </div>

          <div className="p-4 space-y-4">

            {/* Type cards */}
            <div>
              <p className="text-[10px] font-semibold text-[#374151] uppercase tracking-wider mb-2">
                What kind of dataset is this?
              </p>
              <div className="flex gap-2">
                {DATASET_TYPES.map(dt => (
                  <button
                    key={dt.id}
                    onClick={() => setDatasetType(dt.id)}
                    className={`flex-1 px-3 py-2.5 rounded-lg border text-left transition-all
                      ${datasetType === dt.id
                        ? "border-[#7C3AED] bg-[#F5F3FF]"
                        : "border-[#E5E3DC] bg-white hover:border-[#C4B5FD]"}`}
                  >
                    <p className={`text-[12px] font-semibold ${datasetType === dt.id ? "text-[#7C3AED]" : "text-[#374151]"}`}>
                      {dt.label}
                    </p>
                    <p className="text-[10px] text-[#9CA3AF] mt-0.5">{dt.sub}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Focus brand */}
            <div>
              <label className="text-[10px] font-semibold text-[#374151] uppercase tracking-wider block mb-1.5">
                Focus Brand
                <span className="text-[#9CA3AF] font-normal normal-case ml-1">(used as strong prior on every row)</span>
              </label>
              <input
                type="text"
                value={focusBrand}
                onChange={e => setFocusBrand(e.target.value)}
                placeholder="e.g. Coca-Cola"
                className="w-full px-3 py-2 text-[12px] border border-[#E5E3DC] rounded-lg bg-white focus:outline-none focus:border-[#7C3AED] focus:ring-1 focus:ring-[#7C3AED]/20 placeholder:text-[#C4C2BB]"
              />
            </div>

            {/* Anything AI should know */}
            <div>
              <label className="text-[10px] font-semibold text-[#374151] uppercase tracking-wider block mb-1.5">
                Anything the AI should know?
                <span className="text-[#9CA3AF] font-normal normal-case ml-1">(optional — what to expect, special angles, known issues)</span>
              </label>
              <textarea
                value={additionalContext}
                onChange={e => setAdditionalContext(e.target.value)}
                rows={3}
                placeholder={`e.g. These are reviews from frequent flyers focused on lounge experience. Watch for indirect praise that's actually sarcasm. Severity should weight delays > food quality.`}
                className="w-full px-3 py-2 text-[12px] border border-[#E5E3DC] rounded-lg bg-white focus:outline-none focus:border-[#7C3AED] focus:ring-1 focus:ring-[#7C3AED]/20 placeholder:text-[#C4C2BB] resize-none"
              />
            </div>

            {/* Quick prompts */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[10px] text-[#9CA3AF] font-medium">Quick prompts:</span>
              {QUICK_PROMPTS.map(qp => (
                <button
                  key={qp}
                  onClick={() => setAdditionalContext(prev => prev ? prev + ", " + qp : qp)}
                  className="text-[10px] px-2 py-0.5 bg-[#F3F2EE] hover:bg-[#EDE9FE] hover:text-[#7C3AED] text-[#6B7280] rounded-full border border-[#E5E3DC] transition-colors"
                >
                  {qp}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Upload company logo (optional stub) ───────────────────── */}
      {sessionId && (
        <div className="flex items-center justify-between px-4 py-3 bg-white border border-[#E5E3DC] rounded-xl">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#F3F2EE] flex items-center justify-center text-[#9CA3AF] text-xs font-bold">T</div>
            <div>
              <p className="text-[12px] font-medium text-[#374151]">Upload a company logo <span className="text-[#9CA3AF] font-normal">(optional)</span></p>
              <p className="text-[10px] text-[#9CA3AF]">PNG, SVG, or JPEG, used in PDF and PPT exports.</p>
            </div>
          </div>
          <button className="text-[11px] font-medium text-[#7C3AED] hover:underline">Upload logo</button>
        </div>
      )}

      {/* ── Footer: row count + continue ──────────────────────────── */}
      {sessionId && (
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-[#9CA3AF]">{rowCount} rows across 1 file</span>
          <button
            onClick={handleContinue}
            className="flex items-center gap-2 px-4 py-2 bg-[#7C3AED] hover:bg-[#6D28D9] text-white text-[12px] font-semibold rounded-lg transition-colors shadow-sm"
          >
            Continue to scheme mapping
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
