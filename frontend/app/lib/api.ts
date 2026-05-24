const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const log = (msg: string, data?: unknown) => {
  const ts = new Date().toISOString().slice(11, 23);
  if (data !== undefined) console.log(`[E-AI ${ts}] ${msg}`, data);
  else console.log(`[E-AI ${ts}] ${msg}`);
};

async function apiFetch(url: string, opts?: RequestInit) {
  log(`→ ${opts?.method ?? "GET"} ${url}`);
  try {
    const res = await fetch(url, opts);
    if (!res.ok) {
      const body = await res.text();
      log(`✗ ${res.status} ${url}`, body);
      throw new Error(`API ${res.status}: ${body}`);
    }
    const data = await res.json();
    log(`✓ ${url}`, data);
    return data;
  } catch (err) {
    log(`✗ fetch error ${url}`, err);
    throw err;
  }
}

export async function uploadFile(file: File) {
  log(`Uploading file: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`);
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.text();
    log(`✗ Upload failed ${res.status}`, body);
    throw new Error(`Upload failed (${res.status}): ${body}`);
  }
  const data = await res.json();
  log(`✓ Upload complete`, { session_id: data.session_id, rows: data.row_count });
  return data;
}

export async function setContext(payload: {
  session_id: string;
  dataset_type: string;
  focus_brand: string;
  additional_context: string;
}) {
  return apiFetch(`${BASE}/context`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function setSchema(payload: {
  session_id: string;
  primary_text_column: string;
  visible_columns: string[];
  ai_columns: string[];
}) {
  return apiFetch(`${BASE}/schema`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function runTagging(payload: {
  session_id: string;
  provider: string;
  api_key?: string;
  model?: string;
  report_type?: string;
}) {
  return apiFetch(`${BASE}/run-tagging`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: "", ...payload }),
  });
}

export interface ReportTypeInfo {
  id: string;
  name: string;
  description: string;
}

export async function getReportTypes(): Promise<{ report_types: ReportTypeInfo[]; default: string }> {
  return apiFetch(`${BASE}/report-types`);
}

export async function getStatus(session_id: string) {
  const res = await fetch(`${BASE}/session/${session_id}/status`);
  if (!res.ok) throw new Error(`Status check failed: ${res.status}`);
  return res.json();
}

export async function getResults(session_id: string) {
  const res = await fetch(`${BASE}/session/${session_id}/results`);
  if (!res.ok) throw new Error(`Results fetch failed: ${res.status}`);
  return res.json();
}

export async function listRuns() {
  return apiFetch(`${BASE}/runs`);
}

export async function getRun(run_id: string) {
  return apiFetch(`${BASE}/runs/${run_id}`);
}

export async function getRunResults(run_id: string) {
  return apiFetch(`${BASE}/runs/${run_id}`);
}

export function exportUrl(session_id: string, format: "csv" | "xlsx" | "json") {
  return `${BASE}/session/${session_id}/export/${format}`;
}

export async function updateRow(session_id: string, row_idx: number, col: string, value: string) {
  return apiFetch(`${BASE}/session/${session_id}/row/${row_idx}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ col, value }),
  });
}
