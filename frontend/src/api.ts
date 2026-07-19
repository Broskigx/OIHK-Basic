import type {
  AssistantChatResponse,
  AssistantMessage,
  AutoInvestigateResult,
  CaseMemory,
  CaseMonitor,
  CaseRead,
  CarveResult,
  CorrelationQueryResult,
  CustodyReport,
  GraphAnalytics,
  GraphEdge,
  GraphEntityCreate,
  GraphExpandResult,
  GraphNode,
  GraphRead,
  GraphRelationshipCreate,
  CsvImportResult,
  IngestResult,
  MachineRunResult,
  MachineSpec,
  TransformCatalog,
  OsintLookupResult,
  AuditEvent,
  SearchHit,
  SearchRun,
  SourceRead,
  TargetIntakeResult,
  TargetPhoto,
  TargetProfile,
  TokenResponse,
  User,
  ForensicReport,
  ForensicCoreReport,
  HashSetImportResult,
  HashSetInfo,
  HashLookupResult,
  InterestingRule,
  EntityDossier,
} from "./types";

function configuredApiUrl(): string {
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL;
  return "http://127.0.0.1:8000";
}

export const API_URL = configuredApiUrl().replace(/\/$/, "");

let memoryToken: string | null = null;

if (typeof localStorage !== "undefined") localStorage.removeItem("oihk_basic.token");

export function getToken(): string | null {
  return memoryToken;
}

export async function hydrateToken(): Promise<void> {
  memoryToken = null;
}

export async function setToken(token: string): Promise<void> {
  if (!token || token.length > 16_384) throw new Error("Invalid session token");
  memoryToken = token;
}

export async function clearToken(): Promise<void> {
  memoryToken = null;
}

function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)oihk_basic_csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}

function authHeaders(extra?: HeadersInit): HeadersInit {
  const token = getToken();
  return {
    ...(extra ?? {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

function csrfSafeMethod(method?: string): boolean {
  return !method || ["GET", "HEAD", "OPTIONS", "TRACE"].includes(method.toUpperCase());
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = init?.method ?? "GET";
  const csrfToken = csrfSafeMethod(method) ? "" : getCsrfToken();
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: authHeaders({
      "Content-Type": "application/json",
      ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      ...(init?.headers ?? {}),
    }),
  });
  if (response.status === 401) {
    void clearToken();
    throw new Error("Session expired. Sign in again.");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof payload.detail === "string" ? payload.detail : "Request failed");
  }
  return response.json() as Promise<T>;
}

async function requestForm<T>(path: string, body: FormData): Promise<T> {
  const csrfToken = getCsrfToken();
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    body,
    credentials: "include",
    headers: authHeaders({
      ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
    }),
  });
  if (response.status === 401) {
    void clearToken();
    throw new Error("Session expired. Sign in again.");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof payload.detail === "string" ? payload.detail : "Request failed");
  }
  return response.json() as Promise<T>;
}

// --- Authentication ---
export function register(payload: { email: string; username: string; password: string }): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify(payload) });
}

export function login(payload: { email: string; password: string }): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(payload) });
}

export function me(): Promise<User> {
  return request<User>("/auth/me");
}

// --- Cases ---
export function listCases(): Promise<CaseRead[]> {
  return request<CaseRead[]>("/cases");
}

export function createCase(payload: { title: string; summary: string; legal_basis: string; scope_statement: string }): Promise<CaseRead> {
  return request<CaseRead>("/cases", { method: "POST", body: JSON.stringify(payload) });
}

// --- Sources ---
export function listSources(caseId: string): Promise<SourceRead[]> {
  return request<SourceRead[]>(`/sources/${caseId}`);
}

export function ingestText(payload: { case_id: string; title: string; body: string; citation: string; license: string; reliability: number }): Promise<IngestResult> {
  return request<IngestResult>("/sources/text", { method: "POST", body: JSON.stringify(payload) });
}

export function ingestUrl(payload: { case_id: string; url: string; title?: string; license: string; reliability: number }): Promise<IngestResult> {
  return request<IngestResult>("/sources/url", { method: "POST", body: JSON.stringify(payload) });
}

// --- Targets ---
export function targetIntake(payload: { first_name: string; last_name: string; aliases: string; notes: string; legal_basis: string; scope_statement: string; consent_basis: string; auto_search: boolean; photos: File[] }): Promise<TargetIntakeResult> {
  const body = new FormData();
  body.append("first_name", payload.first_name);
  body.append("last_name", payload.last_name);
  body.append("aliases", payload.aliases);
  body.append("notes", payload.notes);
  body.append("legal_basis", payload.legal_basis);
  body.append("scope_statement", payload.scope_statement);
  body.append("consent_basis", payload.consent_basis);
  body.append("auto_search", String(payload.auto_search));
  payload.photos.forEach((file) => body.append("photos", file));
  return requestForm<TargetIntakeResult>("/targets/intake", body);
}

export function listTargets(caseId: string): Promise<TargetProfile[]> {
  return request<TargetProfile[]>(`/targets/case/${caseId}`);
}

export function listTargetMemory(targetId: string): Promise<CaseMemory[]> {
  return request<CaseMemory[]>(`/targets/${targetId}/memory`);
}

export function listTargetPhotos(targetId: string): Promise<TargetPhoto[]> {
  return request<TargetPhoto[]>(`/targets/${targetId}/photos`);
}

export function targetPhotoUrl(targetId: string, photoId: string): string {
  return `${API_URL}/targets/${targetId}/photos/${photoId}/file`;
}

export function uploadTargetPhotos(targetId: string, photos: File[]): Promise<TargetPhoto[]> {
  const body = new FormData();
  photos.forEach((file) => body.append("photos", file));
  return requestForm<TargetPhoto[]>(`/targets/${targetId}/photos`, body);
}

export function listSearchRuns(targetId: string): Promise<SearchRun[]> {
  return request<SearchRun[]>(`/targets/${targetId}/search-runs`);
}

export function listSearchHits(runId: string): Promise<SearchHit[]> {
  return request<SearchHit[]>(`/targets/search-runs/${runId}/hits`);
}

export function rerunTargetSearch(targetId: string): Promise<TargetIntakeResult> {
  return request<TargetIntakeResult>(`/targets/${targetId}/search`, { method: "POST" });
}

// --- Graph ---
export function getGraph(caseId: string): Promise<GraphRead> {
  return request<GraphRead>(`/graph/${caseId}`);
}

export function getGraphAnalytics(caseId: string): Promise<GraphAnalytics> {
  return request<GraphAnalytics>(`/graph/${caseId}/analytics`);
}

export function createGraphEntity(payload: GraphEntityCreate): Promise<GraphNode> {
  return request<GraphNode>("/graph/entities", { method: "POST", body: JSON.stringify(payload) });
}

export function createGraphRelationship(payload: GraphRelationshipCreate): Promise<GraphEdge> {
  return request<GraphEdge>("/graph/relationships", { method: "POST", body: JSON.stringify(payload) });
}

export function expandEntity(entityId: string): Promise<GraphExpandResult> {
  return request<GraphExpandResult>(`/graph/entities/${entityId}/expand`, { method: "POST" });
}

export function renameEntity(entityId: string, label: string): Promise<GraphNode> {
  return request<GraphNode>(`/graph/entities/${entityId}`, { method: "PATCH", body: JSON.stringify({ label }) });
}

export function getEntityDossier(entityId: string): Promise<EntityDossier> {
  return request<EntityDossier>(`/graph/entities/${entityId}/dossier`);
}

export function deleteGraphEntity(entityId: string): Promise<{ deleted: boolean; entity_id: string; relationship_count: number }> {
  return request(`/graph/entities/${encodeURIComponent(entityId)}`, { method: "DELETE" });
}

export function importGraphCsv(caseId: string, csv: string): Promise<CsvImportResult> {
  return request<CsvImportResult>(`/graph/${caseId}/import/csv`, { method: "POST", body: JSON.stringify({ csv }) });
}

export async function fetchGraphExport(caseId: string, kind: "graphml" | "csv-nodes" | "csv-edges"): Promise<Blob> {
  const path = kind === "graphml" ? `/graph/${caseId}/export.graphml` : `/graph/${caseId}/export.csv?kind=${kind === "csv-edges" ? "edges" : "nodes"}`;
  const response = await fetch(`${API_URL}${path}`, { headers: authHeaders(), credentials: "include" });
  if (response.status === 401) {
    void clearToken();
    throw new Error("Session expired. Sign in again.");
  }
  if (!response.ok) throw new Error("Export failed");
  return response.blob();
}

// --- Transforms ---
export function listTransforms(inputType?: string, enabledOnly = true): Promise<TransformCatalog> {
  const params = new URLSearchParams();
  if (inputType) params.set("input", inputType);
  if (enabledOnly) params.set("enabled_only", "true");
  return request<TransformCatalog>(`/transforms?${params.toString()}`);
}

export function runTransform(transformId: string, entityId: string): Promise<GraphExpandResult> {
  return request<GraphExpandResult>(`/transforms/${encodeURIComponent(transformId)}/run`, {
    method: "POST", body: JSON.stringify({ entity_id: entityId }),
  });
}

export function listMachines(inputType?: string): Promise<MachineSpec[]> {
  const params = new URLSearchParams();
  if (inputType) params.set("input", inputType);
  return request<MachineSpec[]>(`/transforms/machines?${params.toString()}`);
}

export function runMachine(machineId: string, entityId: string): Promise<MachineRunResult> {
  return request<MachineRunResult>(`/transforms/machines/${machineId}/run/${entityId}`, { method: "POST" });
}

// --- OSINT ---
export function osintLookup(payload: { case_id: string; value: string }): Promise<OsintLookupResult> {
  return request<OsintLookupResult>("/osint/lookup", { method: "POST", body: JSON.stringify(payload) });
}

// --- Forensics ---
export function analyzeForensics(caseId: string, file: File): Promise<ForensicReport> {
  const body = new FormData();
  body.append("case_id", caseId);
  body.append("file", file);
  return requestForm<ForensicReport>("/forensics/analyze", body);
}

export function analyzeForensicCore(caseId: string, file: File): Promise<ForensicCoreReport> {
  const body = new FormData();
  body.append("case_id", caseId);
  body.append("file", file);
  return requestForm<ForensicCoreReport>("/forensic-core/analyze", body);
}

// --- Custody ---
export function getCustody(caseId: string): Promise<CustodyReport> {
  return request<CustodyReport>(`/custody/${caseId}`);
}

// --- Reports ---
export function reportUrl(caseId: string): string {
  return `${API_URL}/reports/${caseId}.md`;
}

export async function downloadReport(caseId: string): Promise<Blob> {
  const response = await fetch(reportUrl(caseId), { headers: authHeaders(), credentials: "include" });
  if (response.status === 401) {
    void clearToken();
    throw new Error("Session expired. Sign in again.");
  }
  if (!response.ok) throw new Error("Report download failed");
  return response.blob();
}

// --- Audit ---
export function listAuditEvents(caseId?: string, limit = 80): Promise<AuditEvent[]> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (caseId) params.set("case_id", caseId);
  return request<AuditEvent[]>(`/operations/audit?${params.toString()}`);
}

// --- Case Monitoring ---
export function getCaseMonitor(caseId: string): Promise<CaseMonitor> {
  return request<CaseMonitor>(`/operations/cases/${caseId}/monitor`);
}

// --- Core Forensics ---
export function importHashSet(payload: { set_name: string; category: "notable" | "known_good"; severity: string; hashes: string }): Promise<HashSetImportResult> {
  return request<HashSetImportResult>("/forensic-core/hashsets/import", { method: "POST", body: JSON.stringify(payload) });
}

export function listHashSets(): Promise<HashSetInfo[]> {
  return request<HashSetInfo[]>("/forensic-core/hashsets");
}

export function lookupHash(value: string): Promise<HashLookupResult> {
  return request<HashLookupResult>("/forensic-core/hashsets/lookup", { method: "POST", body: JSON.stringify({ value }) });
}

export function carveFile(caseId: string, file: File): Promise<CarveResult> {
  const body = new FormData();
  body.append("case_id", caseId);
  body.append("file", file);
  return requestForm<CarveResult>("/forensic-core/carve", body);
}

export function listInterestingRules(): Promise<InterestingRule[]> {
  return request<InterestingRule[]>("/forensic-core/interesting-rules");
}

export function createInterestingRule(payload: { name: string; severity: string; extensions?: string[]; types?: string[]; description?: string }): Promise<InterestingRule> {
  return request<InterestingRule>("/forensic-core/interesting-rules", { method: "POST", body: JSON.stringify(payload) });
}

export function deleteInterestingRule(ruleId: string): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>(`/forensic-core/interesting-rules/${ruleId}`, { method: "DELETE" });
}
