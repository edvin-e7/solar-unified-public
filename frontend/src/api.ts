export const STORAGE_KEY_API_URL = "solar.apiUrl";

function readBase(): string {
  const env = import.meta.env.VITE_API_URL ?? "";
  let override: string | null = null;
  try {
    override = window.localStorage.getItem(STORAGE_KEY_API_URL);
  } catch {
    // sandboxed iframe / SSR — localStorage throws SecurityError; fall through
  }
  return (override?.trim() || env).replace(/\/$/, "");
}

const BASE = readBase();

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export interface Prospect {
  id?: number;
  address: string;
  lat?: number | null;
  lng?: number | null;
  status?: string;
  score?: number | null;
  annual_kwh?: number | null;
  owner_name?: string | null;
  owner_age?: number | null;
  owner_phone?: string | null;
  notes?: string | null;
}

export interface AgentStatus {
  name: string;
  state: string;
  suggestions: number;
  auto_full_actions: number;
  last_run?: string | null;
}

export interface LeaderboardEntry {
  rank: number;
  agent: string;
  score: number;
}

export interface JournalEntry {
  ts: string;
  phase: string;
  outcome: string;
  lesson: string;
}

export interface BulkImportResult {
  created: number;
  skipped: number;
  errors: string[];
}

export interface Stats {
  total: number;
  by_status: Record<string, number>;
  avg_score: number;
  conversion_rate: number;
  enrichment_rate: number;
  daily: { day: string; n: number }[];
}

export interface PanelCatalogItem {
  id: number;
  address: string;
  owner_name: string | null;
  owner_age: number | null;
  owner_phone: string | null;
  panel_confidence: number | null;
  score: number | null;
  annual_kwh: number | null;
  status: string | null;
  detected_at: string | null;
  lat: number | null;
  lng: number | null;
  notes: string | null;
}

export interface PanelCatalogResponse {
  count: number;
  min_confidence: number;
  items: PanelCatalogItem[];
}

export interface PanelStats {
  total_panel_owners: number;
  high_confidence: number;
  contact_enriched: number;
}

export const api = {
  health: () => request<{ status: string }>("/api/health"),
  settingsFlags: () =>
    request<{ allow_external_llm: boolean; allow_google_solar_api: boolean }>(
      "/api/settings/flags",
    ),
  listProspects: () => request<Prospect[]>("/api/prospects"),
  searchProspects: (params: {
    q?: string;
    status?: string;
    min_score?: number;
    max_score?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    if (params.status) qs.set("status", params.status);
    if (params.min_score != null) qs.set("min_score", String(params.min_score));
    if (params.max_score != null) qs.set("max_score", String(params.max_score));
    return request<Prospect[]>(`/api/prospects?${qs.toString()}`);
  },
  createProspect: (p: Prospect) =>
    request<Prospect>("/api/prospects", { method: "POST", body: JSON.stringify(p) }),
  updateProspect: (id: number, p: Prospect) =>
    request<Prospect>(`/api/prospects/${id}`, { method: "PUT", body: JSON.stringify(p) }),
  deleteProspect: (id: number) =>
    request<{ ok: boolean }>(`/api/prospects/${id}`, { method: "DELETE" }),
  bulkImportCsv: (csvText: string) =>
    request<BulkImportResult>("/api/prospects/bulk-csv", {
      method: "POST",
      body: JSON.stringify({ csv_text: csvText }),
    }),
  exportCsvUrl: () => `${BASE}/api/prospects/export/csv`,
  stats: () => request<Stats>("/api/prospects/stats"),
  bulkStatus: (ids: number[], status: string) =>
    request<{ updated: number }>("/api/prospects/bulk-status", {
      method: "POST",
      body: JSON.stringify({ ids, status }),
    }),
  bulkDelete: (ids: number[]) =>
    request<{ deleted: number }>("/api/prospects/bulk-delete", {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),
  bulkGeocode: (ids: number[]) =>
    request<{
      changed: number;
      unchanged: number;
      errors: { id: number; address: string; error: string }[];
    }>("/api/prospects/bulk-geocode", { method: "POST", body: JSON.stringify({ ids }) }),
  bulkEnrichContacts: (ids: number[], minScore = 0.6) =>
    request<{
      changed: number;
      unchanged: number;
      no_match: number;
      errors: { id: number; address: string; error_kind: string; error: string }[];
    }>("/api/prospects/bulk-enrich-contacts", {
      method: "POST",
      body: JSON.stringify({ ids, min_score: minScore }),
    }),
  detect: (address: string) =>
    request<Record<string, unknown>>("/api/detect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ address }),
    }),
  solarPotential: (lat: number, lng: number) =>
    request<{ source: string; annual_kwh: number; annual_sek: number }>("/api/solar/potential", {
      method: "POST",
      body: JSON.stringify({ lat, lng }),
    }),
  enrichPerson: (address: string, name?: string) =>
    request<{ name: string | null; age: number | null; phone: string | null }>(
      "/api/enrich/person",
      { method: "POST", body: JSON.stringify({ address, name }) },
    ),
  agentsStatus: () => request<{ agents: AgentStatus[] }>("/api/agents/status"),
  leaderboard: () => request<LeaderboardEntry[]>("/api/agents/leaderboard"),
  journalTail: (limit = 50) =>
    request<{ entries: JournalEntry[] }>(`/api/execute/status?limit=${limit}`),
  runLearningCycle: () =>
    request<{ ok: boolean }>("/api/execute/learning-only", { method: "POST" }),
  generatePitch: (payload: {
    owner_name: string;
    address: string;
    annual_kwh: number;
    annual_sek: number;
  }) =>
    request<{ pitch: string }>("/api/agents/pitch", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  panelCatalog: (minConfidence = 0.6, limit = 5000) =>
    request<PanelCatalogResponse>(
      `/api/panels/catalog?min_confidence=${minConfidence}&limit=${limit}`,
    ),
  panelStats: () => request<PanelStats>("/api/panels/stats"),
  panelCatalogXlsxUrl: (minConfidence = 0.6) =>
    `${BASE}/api/panels/catalog.xlsx?min_confidence=${minConfidence}`,
};
