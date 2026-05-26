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

export async function refineReport(session_id: string, feedback: string, design_theme: string) {
  return apiFetch(`${BASE}/session/${session_id}/refine-report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback, design_theme }),
  });
}

// ── Skill Registry ──────────────────────────────────────────────────────────

export interface SkillInfo {
  id: string;
  name: string;
  description: string;
  type: string;
  builtin: boolean;
  trigger_words?: string[];
}

export async function listSkills(): Promise<{ skills: SkillInfo[] }> {
  return apiFetch(`${BASE}/skills`);
}

export async function getSkill(skillId: string): Promise<SkillInfo> {
  return apiFetch(`${BASE}/skills/${skillId}`);
}

export async function uploadSkill(skillData: {
  name: string;
  description?: string;
  trigger_words?: string[];
}): Promise<{ ok: boolean; skill: SkillInfo }> {
  return apiFetch(`${BASE}/skills/upload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(skillData),
  });
}

export async function deleteSkill(skillId: string): Promise<{ ok: boolean; deleted: string }> {
  return apiFetch(`${BASE}/skills/${skillId}`, { method: "DELETE" });
}

export async function matchSkills(prompt: string): Promise<{ matches: SkillInfo[] }> {
  return apiFetch(`${BASE}/skills/match`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
  });
}

// ── Template Library ────────────────────────────────────────────────────────

export interface TemplateInfo {
  id: string;
  name: string;
  description: string;
  builtin: boolean;
  report_types: string[];
  tags: string[];
}

export async function listTemplates(): Promise<{ templates: TemplateInfo[] }> {
  return apiFetch(`${BASE}/templates`);
}

export async function getTemplate(templateId: string): Promise<TemplateInfo> {
  return apiFetch(`${BASE}/templates/${templateId}`);
}

export async function uploadTemplate(payload: {
  name: string;
  html_content: string;
  description?: string;
  report_types?: string[];
  tags?: string[];
}): Promise<{ ok: boolean; template: TemplateInfo }> {
  return apiFetch(`${BASE}/templates/upload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// ── Methodology ─────────────────────────────────────────────────────────────

export async function getMethodology(): Promise<Record<string, unknown>> {
  return apiFetch(`${BASE}/methodology`);
}

export async function getMethodologySteps(): Promise<{ steps: Array<{ id: number; name: string; description: string; agent_action: string }> }> {
  return apiFetch(`${BASE}/methodology/steps`);
}

// ── Skill Memory ───────────────────────────────────────────────────────────

export async function learnFromRun(sessionId: string): Promise<{ ok: boolean; learned: boolean; skill?: SkillInfo; message?: string }> {
  return apiFetch(`${BASE}/skills/learn-from-run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export async function getLearnedPreferences(): Promise<{
  total_runs: number;
  preferred_report_type: string | null;
  preferred_provider: string | null;
  preferred_design_theme: string | null;
  report_type_counts: Record<string, number>;
  provider_counts: Record<string, number>;
  design_theme_counts: Record<string, number>;
  refinement_feedback_count: number;
}> {
  return apiFetch(`${BASE}/skills/learned-preferences`);
}

// ── Design Connector ───────────────────────────────────────────────────────

export interface DesignTool {
  id: string;
  name: string;
  status: string;
  capabilities: string[];
}

export async function listDesignTools(): Promise<{ tools: DesignTool[] }> {
  return apiFetch(`${BASE}/design/tools`);
}

export async function applyDesignTheme(payload: {
  html_content: string;
  theme?: string;
  brand_config?: Record<string, string>;
}): Promise<{ ok: boolean; html_content: string }> {
  return apiFetch(`${BASE}/design/apply-theme`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
