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

// ── Sessions (lightweight metadata for picking runs to compare) ────────────

export interface SessionInfo {
  session_id: string;
  filename: string | null;
  status: string;
  report_type: string | null;
  focus_brand: string;
  row_count: number;
  analyzed_count: number;
  has_report: boolean;
  is_demo: boolean;
  demo_id: string | null;
  created_at: string | null;
  updated_at: string | null;
  run_id: string | null;
}

export async function listSessions(): Promise<{ sessions: SessionInfo[]; count: number }> {
  return apiFetch(`${BASE}/sessions`);
}

// ── Comparison ─────────────────────────────────────────────────────────────

export interface CompareFinding {
  claim: string;
  confidence: string;
  so_what: string;
}

export interface CompareThemeBucket {
  name: string;
  count: number;
}

export interface CompareEvidence {
  quote: string;
  source: string;
  sentiment: string;
}

export interface CompareRun {
  session_id: string;
  agent: string;
  filename: string;
  title: string;
  subtitle: string;
  executive_one_liner: string;
  findings: CompareFinding[];
  themes: CompareThemeBucket[];
  sentiments: CompareThemeBucket[];
  evidence: CompareEvidence[];
  recommendations: string[];
}

export interface CompareOverlapTheme {
  name: string;
  session_ids: string[];
  run_count: number;
}

export interface CompareOverlapFinding {
  claim: string;
  session_ids: string[];
  run_count: number;
}

export interface CompareDivergence {
  name: string;
  session_id: string;
  agent: string;
}

export interface ComparisonResult {
  runs: CompareRun[];
  overlaps: {
    themes: CompareOverlapTheme[];
    findings: CompareOverlapFinding[];
  };
  divergences: CompareDivergence[];
  synthesis: string;
}

export async function compareRuns(sessionIds: string[]): Promise<ComparisonResult> {
  return apiFetch(`${BASE}/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_ids: sessionIds }),
  });
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

export interface MemoryInsights {
  total_runs: number;
  preferred_report_type: string | null;
  preferred_provider: string | null;
  preferred_design_theme: string | null;
  report_type_counts: Record<string, number>;
  provider_counts: Record<string, number>;
  design_theme_counts: Record<string, number>;
  refinement_feedback_count: number;
  refinement_patterns: string[];
  dataset_domain_counts: Record<string, number>;
  avg_duration_seconds: number | null;
  avg_findings_per_report: number | null;
  avg_refinements_per_run: number;
  recent_outcomes: Array<Record<string, unknown>>;
}

export async function getMemoryInsights(): Promise<MemoryInsights> {
  return apiFetch(`${BASE}/memory/insights`);
}

export async function resetMemory(): Promise<{ ok: boolean; cleared_runs: number }> {
  return apiFetch(`${BASE}/memory/reset`, { method: "POST" });
}

// ── MCP Connectors ────────────────────────────────────────────────────────

export interface MCPConfigField {
  key: string;
  label: string;
  type: "text" | "password";
  required: boolean;
  placeholder?: string;
}

export interface MCPConnector {
  id: string;
  name: string;
  category: string;
  icon: string;
  description: string;
  status: "available" | "coming_soon" | "active";
  requires: string[];
  config_fields: MCPConfigField[];
  enabled: boolean;
  user_config: Record<string, string>;
  always_enabled?: boolean;
}

export async function listMCPConnectors(): Promise<{ connectors: MCPConnector[] }> {
  return apiFetch(`${BASE}/mcp/connectors`);
}

export async function getMCPConnector(id: string): Promise<MCPConnector> {
  return apiFetch(`${BASE}/mcp/connectors/${id}`);
}

export async function enableMCPConnector(id: string, config: Record<string, string>): Promise<{ ok: boolean; connector: MCPConnector }> {
  return apiFetch(`${BASE}/mcp/connectors/${id}/enable`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  });
}

export async function disableMCPConnector(id: string): Promise<{ ok: boolean; connector: MCPConnector }> {
  return apiFetch(`${BASE}/mcp/connectors/${id}/disable`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}

export async function testMCPConnector(id: string): Promise<{ connector_id: string; success: boolean; message: string }> {
  return apiFetch(`${BASE}/mcp/connectors/${id}/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}

export async function getActiveMCPConnectors(): Promise<{ connectors: MCPConnector[] }> {
  return apiFetch(`${BASE}/mcp/active`);
}

// ── Connector data pulls ──────────────────────────────────────────────────

export interface ConnectorRow {
  text: string;
  url: string;
  platform: string;
  date: string;
  author: string;
  metadata: Record<string, unknown>;
}

export async function searchConnector(
  connectorId: string,
  query: string,
  limit: number,
  filters: Record<string, unknown> = {},
): Promise<{ rows: ConnectorRow[]; row_count: number }> {
  return apiFetch(`${BASE}/connectors/${connectorId}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit, filters }),
  });
}

export async function searchConnectorToSession(
  connectorId: string,
  query: string,
  limit: number,
  filters: Record<string, unknown> = {},
): Promise<{
  session_id: string;
  row_count: number;
  filename: string;
  columns: string[];
  preview: ConnectorRow[];
}> {
  return apiFetch(`${BASE}/connectors/${connectorId}/search-to-session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit, filters }),
  });
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
