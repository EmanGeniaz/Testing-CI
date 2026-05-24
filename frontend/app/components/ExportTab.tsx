"use client";
import { exportUrl } from "../lib/api";

interface ExportTabProps {
  sessionId: string;
  rowCount: number;
  filename: string;
}

export default function ExportTab({ sessionId, rowCount, filename }: ExportTabProps) {
  const formats = [
    {
      id: "csv" as const,
      label: "Export as CSV",
      ext: "CSV",
      desc: "Comma-separated, compatible with Excel, Google Sheets, Tableau.",
      iconColor: "text-emerald-600",
      badgeClass: "bg-emerald-100 text-emerald-700",
    },
    {
      id: "xlsx" as const,
      label: "Export as Excel (XLSX)",
      ext: "XLSX",
      desc: "Microsoft Excel workbook with formatted columns, ready for stakeholder distribution.",
      iconColor: "text-blue-600",
      badgeClass: "bg-blue-100 text-blue-700",
    },
    {
      id: "json" as const,
      label: "Export as JSON",
      ext: "JSON",
      desc: "Full structured JSON with nested XAI rationale objects, ideal for APIs or pipelines.",
      iconColor: "text-amber-600",
      badgeClass: "bg-amber-100 text-amber-700",
    },
  ];

  return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      {/* Header */}
      <div className="text-center mb-10">
        <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-[#EDE9FE] flex items-center justify-center">
          <svg className="w-7 h-7 text-[#7C3AED]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
        </div>
        <h1 className="text-[22px] font-bold text-[#111827]">Export your analysis</h1>
        <p className="text-[13px] text-[#6B7280] mt-1">
          <span className="font-semibold text-[#374151]">{rowCount} rows</span> of AI-tagged data from{" "}
          <span className="font-semibold text-[#374151]">{filename}</span> are ready.
        </p>
      </div>

      <div className="space-y-3">
        {formats.map(fmt => (
          <a
            key={fmt.id}
            href={exportUrl(sessionId, fmt.id)}
            download
            className="flex items-center gap-4 bg-white border border-[#E5E3DC] rounded-xl p-4 hover:border-[#7C3AED] hover:shadow-sm transition-all group"
          >
            <div className="w-11 h-11 rounded-xl bg-[#F8F7F3] flex items-center justify-center flex-shrink-0 group-hover:bg-[#F0EEFF] transition-colors">
              <svg className={`w-5 h-5 ${fmt.iconColor}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 0v10" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-[13px] font-semibold text-[#111827]">{fmt.label}</span>
                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${fmt.badgeClass}`}>{fmt.ext}</span>
              </div>
              <p className="text-[11px] text-[#9CA3AF]">{fmt.desc}</p>
            </div>
            <svg className="w-4 h-4 text-[#7C3AED] opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </a>
        ))}
      </div>

      <p className="mt-8 text-center text-[11px] text-[#9CA3AF]">
        All exports include full XAI rationale columns (text_evidence, theme_reasoning, sentiment_reasoning, signal_reasoning, confidence_reasoning).
      </p>
    </div>
  );
}
