import type {
  AssistantChatResponse,
  AssistantMessage,
  AutoInvestigateResult,
  AutoStreamEvent,
  CaseMemory,
  CaseRead,
  CaseMonitor,
  CopilotConversation,
  CopilotMessage,
  CopilotReply,
  CarveResult,
  CorrelationQueryResult,
  CustodyReport,
  HashLookupResult,
  HashSetImportResult,
  HashSetInfo,
  InterestingRule,
  EntityDossier,
  EvidenceItem,
  EvidenceVerification,
  ForensicCoreReport,
  ForensicReport,
  GraphAnalytics,
  GraphEntityCreate,
  GraphExpandResult,
  GraphNode,
  CsvImportResult,
  GraphRead,
  GraphSnapshot,
  GraphWorkspace,
  IngestResult,
  InvestigateEvent,
  MachineRunResult,
  MachineSpec,
  LocalModelConfiguration,
  LocalModelDescriptor,
  LocalModelProviderId,
  LocalModelServiceProbe,
  OsintLookupResult,
  OsintQuery,
  AuditEvent,
  ApplicationSettings,
  ProviderCatalog,
  ReportDocument,
  ReportSection,
  ReportTemplate,
  SearchHit,
  SearchRun,
  SourceRead,
  StorageStatus,
  TransformCatalog,
  TargetIntakeResult,
  TargetPhoto,
  TargetProfile,
  TokenResponse,
  User,
  InvestigationDraft,
} from "./types";

export let API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export function setApiUrl(url: string): void {
  const parsed = new URL(url);
  if (parsed.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(parsed.hostname)) {
    throw new Error("The managed OIHK API must use a loopback HTTP address.");
  }
  API_URL = parsed.origin;
}

export function getApiUrl(): string {
  return API_URL;
}

const TOKEN_KEY = "oihk.token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/** Read the CSRF token from the ``oihk_csrf_token`` cookie (set by the backend). */
function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)oihk_csrf_token=([^;]*)/);
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
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      credentials: "include",
      headers: authHeaders({
        "Content-Type": "application/json",
        ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
        ...(init?.headers ?? {}),
      }),
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") {
      throw new Error("Operation cancelled");
    }
    if (cause instanceof TypeError && String(cause.message).includes("fetch")) {
      throw new Error("Local service unavailable. OIHK Basic could not connect to its local data service.");
    }
    throw new Error("Network error. Please check your connection and try again.");
  }
  if (response.status === 401) {
    clearToken();
    throw new Error("Session expired. Please sign in again.");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof payload.detail === "string" ? payload.detail : `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function requestForm<T>(path: string, body: FormData, signal?: AbortSignal): Promise<T> {
  const csrfToken = getCsrfToken();
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      body,
      credentials: "include",
      signal,
      headers: authHeaders({
        ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      }),
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw new Error("Operation cancelled");
    if (cause instanceof TypeError && String(cause.message).includes("fetch")) {
      throw new Error("Local service unavailable. OIHK Basic could not connect to its local data service.");
    }
    throw new Error("Network error. Please check your connection and try again.");
  }
  if (response.status === 401) {
    clearToken();
    throw new Error("Session expired. Please sign in again.");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof payload.detail === "string" ? payload.detail : `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

// --- Authentication ---
export function register(payload: {
  email: string;
  username: string;
  password: string;
}): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify(payload) });
}

export function login(payload: { email: string; password: string }): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(payload) });
}

export function me(): Promise<User> {
  return request<User>("/auth/me");
}

// --- AI assistant ---
export function assistantChat(payload: {
  message: string;
  case_id?: string | null;
  target_id?: string | null;
  file?: File | null;
}): Promise<AssistantChatResponse> {
  if (payload.file) {
    const body = new FormData();
    body.append("message", payload.message);
    if (payload.case_id) body.append("case_id", payload.case_id);
    if (payload.target_id) body.append("target_id", payload.target_id);
    body.append("file", payload.file);
    return requestForm<AssistantChatResponse>("/assistant/chat/attachment", body);
  }
  return request<AssistantChatResponse>("/assistant/chat", {
    method: "POST",
    body: JSON.stringify({ message: payload.message, case_id: payload.case_id, target_id: payload.target_id }),
  });
}

export function assistantHistory(caseId: string): Promise<AssistantMessage[]> {
  return request<AssistantMessage[]>(`/assistant/history/${caseId}`);
}

export function listCopilotConversations(
  caseId?: string | null,
  includeArchived = false,
): Promise<CopilotConversation[]> {
  const params = new URLSearchParams({ include_archived: String(includeArchived) });
  if (caseId) params.set("case_id", caseId);
  return request<CopilotConversation[]>(`/assistant/conversations?${params}`);
}

export function createCopilotConversation(payload: {
  case_id?: string | null;
  title?: string;
}): Promise<CopilotConversation> {
  return request<CopilotConversation>("/assistant/conversations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCopilotConversation(
  conversationId: string,
  payload: { title?: string; archived?: boolean },
): Promise<CopilotConversation> {
  return request<CopilotConversation>(`/assistant/conversations/${conversationId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteCopilotConversation(conversationId: string): Promise<void> {
  return request<void>(`/assistant/conversations/${conversationId}`, { method: "DELETE" });
}

export function listCopilotMessages(conversationId: string): Promise<CopilotMessage[]> {
  return request<CopilotMessage[]>(`/assistant/conversations/${conversationId}/messages`);
}

export function sendCopilotMessage(
  conversationId: string,
  content: string,
  signal?: AbortSignal,
): Promise<CopilotReply> {
  return request<CopilotReply>(`/assistant/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content }),
    signal,
  });
}

// Streamed agent investigation: NDJSON events (thought/tool/finding/graph/final).
export async function investigateStream(
  payload: { message: string; case_id?: string | null; target_id?: string | null },
  onEvent: (event: InvestigateEvent) => void,
): Promise<void> {
  const csrfToken = getCsrfToken();
  let response: Response;
  try {
    response = await fetch(`${API_URL}/assistant/investigate/stream`, {
      method: "POST",
      credentials: "include",
      headers: authHeaders({
        "Content-Type": "application/json",
        ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      }),
      body: JSON.stringify({
        message: payload.message,
        case_id: payload.case_id ?? null,
        target_id: payload.target_id ?? null,
      }),
    });
  } catch (cause) {
    if (cause instanceof TypeError && String(cause.message).includes("fetch")) {
      throw new Error("Local service unavailable. OIHK Basic could not connect to its local data service.");
    }
    throw new Error("Network error. Please check your connection and try again.");
  }
  if (response.status === 401) {
    clearToken();
    throw new Error("Session expired. Please sign in again.");
  }
  if (!response.ok || !response.body) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : `Request failed (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const emit = (line: string) => {
    const trimmed = line.trim();
    if (trimmed) onEvent(JSON.parse(trimmed) as InvestigateEvent);
  };
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let newline = buffer.indexOf("\n");
    while (newline >= 0) {
      emit(buffer.slice(0, newline));
      buffer = buffer.slice(newline + 1);
      newline = buffer.indexOf("\n");
    }
  }
  emit(buffer);
}

// --- OIHK AI one-click investigation ---
export function autoInvestigate(payload: {
  first_name: string;
  last_name: string;
  aliases: string;
  notes: string;
}): Promise<AutoInvestigateResult> {
  return request<AutoInvestigateResult>("/targets/auto", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// Streamed one-click: the backend emits NDJSON phase events; onEvent fires per line.
export async function autoInvestigateStream(
  payload: { first_name: string; last_name: string; aliases: string; notes: string },
  onEvent: (event: AutoStreamEvent) => void,
): Promise<void> {
  const csrfToken = getCsrfToken();
  let response: Response;
  try {
    response = await fetch(`${API_URL}/targets/auto/stream`, {
      method: "POST",
      credentials: "include",
      headers: authHeaders({
        "Content-Type": "application/json",
        ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      }),
      body: JSON.stringify(payload),
    });
  } catch (cause) {
    if (cause instanceof TypeError && String(cause.message).includes("fetch")) {
      throw new Error("Local service unavailable. OIHK Basic could not connect to its local data service.");
    }
    throw new Error("Network error. Please check your connection and try again.");
  }
  if (response.status === 401) {
    clearToken();
    throw new Error("Session expired. Please sign in again.");
  }
  if (!response.ok || !response.body) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : `Request failed (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const emit = (line: string) => {
    const trimmed = line.trim();
    if (trimmed) onEvent(JSON.parse(trimmed) as AutoStreamEvent);
  };
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let newline = buffer.indexOf("\n");
    while (newline >= 0) {
      emit(buffer.slice(0, newline));
      buffer = buffer.slice(newline + 1);
      newline = buffer.indexOf("\n");
    }
  }
  emit(buffer);
}

// --- Free OSINT enrichment (DNS / RDAP-WHOIS / crt.sh / GeoIP) ---
export function osintLookup(
  payload: { case_id: string; value: string },
  signal?: AbortSignal,
): Promise<OsintLookupResult> {
  return request<OsintLookupResult>("/osint/lookup", { method: "POST", body: JSON.stringify(payload), signal });
}

export function getOsintHistory(caseId: string): Promise<OsintQuery[]> {
  return request<OsintQuery[]>(`/osint/history/${encodeURIComponent(caseId)}`);
}

export function promoteOsintQuery(queryId: string): Promise<OsintLookupResult> {
  return request<OsintLookupResult>(`/osint/history/${encodeURIComponent(queryId)}/promote`, { method: "POST" });
}

// --- Cryptographic chain of custody ---
export function getCustody(caseId: string): Promise<CustodyReport> {
  return request<CustodyReport>(`/custody/${caseId}`);
}

// --- Forensic media analysis / steganalysis ---
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

export function listCases(): Promise<CaseRead[]> {
  return request<CaseRead[]>("/cases");
}

export function createCase(payload: InvestigationDraft): Promise<CaseRead> {
  return request<CaseRead>("/cases", { method: "POST", body: JSON.stringify(payload) });
}

export function updateCase(caseId: string, payload: Partial<InvestigationDraft> & { status?: string }): Promise<CaseRead> {
  return request<CaseRead>(`/cases/${encodeURIComponent(caseId)}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function duplicateCase(caseId: string): Promise<CaseRead> {
  return request<CaseRead>(`/cases/${encodeURIComponent(caseId)}/duplicate`, { method: "POST" });
}

export function deleteCase(caseId: string): Promise<void> {
  return request<void>(`/cases/${encodeURIComponent(caseId)}`, { method: "DELETE" });
}

export function importCaseDocument(document: unknown): Promise<CaseRead> {
  return request<CaseRead>("/cases/import", { method: "POST", body: JSON.stringify(document) });
}

export async function downloadCaseExport(caseId: string): Promise<Blob> {
  const response = await fetch(`${API_URL}/exports/cases/${encodeURIComponent(caseId)}/json`, { credentials: "include", headers: authHeaders() });
  if (!response.ok) throw new Error(`Could not export investigation (${response.status})`);
  return response.blob();
}

export function getApplicationSettings(): Promise<ApplicationSettings> {
  return request<ApplicationSettings>("/settings");
}

export function saveApplicationSettings(payload: Omit<ApplicationSettings, "id" | "schema_version" | "updated_at">): Promise<ApplicationSettings> {
  return request<ApplicationSettings>("/settings", { method: "PUT", body: JSON.stringify(payload) });
}

export function getStorageStatus(): Promise<StorageStatus> {
  return request<StorageStatus>("/settings/storage");
}

export async function downloadStorageBackup(): Promise<Blob> {
  const response = await fetch(`${API_URL}/settings/backup`, { credentials: "include", headers: authHeaders() });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof payload.detail === "string" ? payload.detail : "Could not create the local backup");
  }
  return response.blob();
}

export function listSources(caseId: string): Promise<SourceRead[]> {
  return request<SourceRead[]>(`/sources/${caseId}`);
}

export function ingestText(payload: {
  case_id: string;
  title: string;
  body: string;
  citation: string;
  license: string;
  reliability: number;
}): Promise<IngestResult> {
  return request<IngestResult>("/sources/text", { method: "POST", body: JSON.stringify(payload) });
}

export function ingestUrl(payload: {
  case_id: string;
  url: string;
  title?: string;
  license: string;
  reliability: number;
}): Promise<IngestResult> {
  return request<IngestResult>("/sources/url", { method: "POST", body: JSON.stringify(payload) });
}

export function getGraph(caseId: string): Promise<GraphRead> {
  return request<GraphRead>(`/graph/${caseId}`);
}

export function getGraphAnalytics(caseId: string): Promise<GraphAnalytics> {
  return request<GraphAnalytics>(`/graph/${caseId}/analytics`);
}

export function createGraphEntity(payload: GraphEntityCreate): Promise<GraphNode> {
  return request<GraphNode>("/graph/entities", { method: "POST", body: JSON.stringify(payload) });
}

export function expandEntity(entityId: string): Promise<GraphExpandResult> {
  return request<GraphExpandResult>(`/graph/entities/${entityId}/expand`, { method: "POST" });
}

// --- Transforms (Maltego-style, run applicable enrichment on a node) ---
export function listTransforms(inputType?: string, enabledOnly = true): Promise<TransformCatalog> {
  const params = new URLSearchParams();
  if (inputType) params.set("input", inputType);
  if (enabledOnly) params.set("enabled_only", "true");
  return request<TransformCatalog>(`/transforms?${params.toString()}`);
}

export function runTransform(transformId: string, entityId: string): Promise<GraphExpandResult> {
  return request<GraphExpandResult>(`/transforms/${encodeURIComponent(transformId)}/run`, {
    method: "POST",
    body: JSON.stringify({ entity_id: entityId }),
  });
}

// --- Machines (deterministic transform chains) ---
export function listMachines(inputType?: string): Promise<MachineSpec[]> {
  const params = new URLSearchParams();
  if (inputType) params.set("input", inputType);
  return request<MachineSpec[]>(`/transforms/machines?${params.toString()}`);
}

export function createMachine(payload: {
  name: string;
  description?: string;
  transform_ids: string[];
  input_type?: string;
}): Promise<MachineSpec> {
  return request<MachineSpec>("/transforms/machines", { method: "POST", body: JSON.stringify(payload) });
}

export function runMachine(machineId: string, entityId: string): Promise<MachineRunResult> {
  return request<MachineRunResult>(`/transforms/machines/${machineId}/run/${entityId}`, { method: "POST" });
}

export function runAdhocMachine(transformIds: string[], entityId: string): Promise<MachineRunResult> {
  return request<MachineRunResult>(`/transforms/machines/run/${entityId}`, {
    method: "POST",
    body: JSON.stringify({ transform_ids: transformIds }),
  });
}

export function renameEntity(entityId: string, label: string): Promise<GraphNode> {
  return request<GraphNode>(`/graph/entities/${entityId}`, {
    method: "PATCH",
    body: JSON.stringify({ label }),
  });
}

export function getEntityDossier(entityId: string): Promise<EntityDossier> {
  return request<EntityDossier>(`/graph/entities/${entityId}/dossier`);
}

// --- Graph import / export ---
export function importGraphCsv(caseId: string, csv: string): Promise<CsvImportResult> {
  return request<CsvImportResult>(`/graph/${caseId}/import/csv`, {
    method: "POST",
    body: JSON.stringify({ csv }),
  });
}

export async function fetchGraphExport(caseId: string, kind: "graphml" | "csv-nodes" | "csv-edges"): Promise<Blob> {
  const path =
    kind === "graphml"
      ? `/graph/${caseId}/export.graphml`
      : `/graph/${caseId}/export.csv?kind=${kind === "csv-edges" ? "edges" : "nodes"}`;
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { headers: authHeaders(), credentials: "include" });
  } catch (cause) {
    if (cause instanceof TypeError && String(cause.message).includes("fetch")) {
      throw new Error("Local service unavailable. OIHK Basic could not connect to its local data service.");
    }
    throw new Error("Network error. Please check your connection and try again.");
  }
  if (response.status === 401) {
    clearToken();
    throw new Error("Session expired. Please sign in again.");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof payload.detail === "string" ? payload.detail : `Export failed (${response.status})`);
  }
  return response.blob();
}

export function updateEntityDetails(
  entityId: string,
  payload: { properties?: Record<string, string>; notes?: string; type?: string },
): Promise<GraphNode> {
  return request<GraphNode>(`/graph/entities/${entityId}/details`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function reportUrl(caseId: string): string {
  return `${API_URL}/reports/${caseId}.md`;
}

export async function downloadReport(caseId: string): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(reportUrl(caseId), { headers: authHeaders(), credentials: "include" });
  } catch (cause) {
    if (cause instanceof TypeError && String(cause.message).includes("fetch")) {
      throw new Error("Local service unavailable. OIHK Basic could not connect to its local data service.");
    }
    throw new Error("Network error. Please check your connection and try again.");
  }
  if (response.status === 401) {
    clearToken();
    throw new Error("Session expired. Please sign in again.");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof payload.detail === "string" ? payload.detail : `Request failed (${response.status})`);
  }
  return response.blob();
}

export function targetIntake(payload: {
  first_name: string;
  last_name: string;
  aliases: string;
  notes: string;
  legal_basis: string;
  scope_statement: string;
  consent_basis: string;
  auto_search: boolean;
  photos: File[];
}): Promise<TargetIntakeResult> {
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

export function getProviderCatalog(): Promise<ProviderCatalog> {
  return request<ProviderCatalog>("/operations/providers");
}

export function listReports(caseId: string): Promise<ReportDocument[]> {
  return request<ReportDocument[]>(`/reports/case/${encodeURIComponent(caseId)}`);
}

export function generateReport(caseId: string, payload: { title: string; format: "markdown" | "html" | "json"; sections: ReportSection[]; methodology: string; limitations: string }): Promise<ReportDocument> {
  return request<ReportDocument>(`/reports/${encodeURIComponent(caseId)}/generate`, { method: "POST", body: JSON.stringify(payload) });
}

export function generateAiReportDraft(caseId: string, payload: { title: string; focus: string }): Promise<ReportDocument> {
  return request<ReportDocument>(`/reports/${encodeURIComponent(caseId)}/ai-draft`, { method: "POST", body: JSON.stringify(payload) });
}

export function approveReport(documentId: string): Promise<ReportDocument> {
  return request<ReportDocument>(`/reports/documents/${encodeURIComponent(documentId)}/approve`, { method: "POST" });
}

export function deleteReport(documentId: string): Promise<void> {
  return request<void>(`/reports/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" });
}

export async function downloadReportDocument(documentId: string): Promise<Blob> {
  const response = await fetch(`${API_URL}/reports/documents/${encodeURIComponent(documentId)}/export`, { credentials: "include", headers: authHeaders() });
  if (!response.ok) throw new Error(`Could not export report (${response.status})`);
  return response.blob();
}

export function listReportTemplates(): Promise<ReportTemplate[]> {
  return request<ReportTemplate[]>("/reports/templates");
}

export function saveReportTemplate(payload: Omit<ReportTemplate, "id" | "created_at" | "updated_at">): Promise<ReportTemplate> {
  return request<ReportTemplate>("/reports/templates", { method: "POST", body: JSON.stringify(payload) });
}

export function deleteReportTemplate(templateId: string): Promise<void> {
  return request<void>(`/reports/templates/${encodeURIComponent(templateId)}`, { method: "DELETE" });
}

export function listEvidence(caseId: string): Promise<EvidenceItem[]> {
  return request<EvidenceItem[]>(`/evidence/${encodeURIComponent(caseId)}`);
}

export function uploadEvidence(caseId: string, file: File, notes = "", tags = "", signal?: AbortSignal): Promise<EvidenceItem> {
  const body = new FormData();
  body.append("case_id", caseId);
  body.append("notes", notes);
  body.append("tags", tags);
  body.append("file", file);
  return requestForm<EvidenceItem>("/evidence", body, signal);
}

export function updateEvidence(itemId: string, payload: { notes?: string; tags?: string[]; entity_ids?: string[] }): Promise<EvidenceItem> {
  return request<EvidenceItem>(`/evidence/items/${encodeURIComponent(itemId)}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function verifyEvidence(itemId: string): Promise<EvidenceVerification> {
  return request<EvidenceVerification>(`/evidence/items/${encodeURIComponent(itemId)}/verify`, { method: "POST" });
}

export function deleteEvidence(itemId: string): Promise<void> {
  return request<void>(`/evidence/items/${encodeURIComponent(itemId)}`, { method: "DELETE" });
}

export function evidencePreviewUrl(itemId: string): string {
  return `${API_URL}/evidence/items/${encodeURIComponent(itemId)}/preview`;
}

export async function downloadEvidenceManifest(caseId: string): Promise<Blob> {
  const response = await fetch(`${API_URL}/evidence/${encodeURIComponent(caseId)}/manifest.json`, { credentials: "include", headers: authHeaders() });
  if (!response.ok) throw new Error(`Could not export evidence manifest (${response.status})`);
  return response.blob();
}

export function updateGraphRelationship(relationshipId: string, payload: { label?: string; confidence?: number }): Promise<GraphRead["edges"][number]> {
  return request<GraphRead["edges"][number]>(`/graph/relationships/${encodeURIComponent(relationshipId)}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteGraphRelationship(relationshipId: string): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>(`/graph/relationships/${encodeURIComponent(relationshipId)}`, { method: "DELETE" });
}

export function getGraphWorkspace(caseId: string): Promise<GraphWorkspace> {
  return request<GraphWorkspace>(`/graph/${encodeURIComponent(caseId)}/workspace`);
}

export function saveGraphWorkspace(caseId: string, workspace: Omit<GraphWorkspace, "id" | "case_id" | "updated_at">): Promise<GraphWorkspace> {
  return request<GraphWorkspace>(`/graph/${encodeURIComponent(caseId)}/workspace`, { method: "PUT", body: JSON.stringify(workspace) });
}

export function listGraphSnapshots(caseId: string): Promise<GraphSnapshot[]> {
  return request<GraphSnapshot[]>(`/graph/${encodeURIComponent(caseId)}/snapshots`);
}

export function createGraphSnapshot(caseId: string, name: string): Promise<GraphSnapshot> {
  return request<GraphSnapshot>(`/graph/${encodeURIComponent(caseId)}/snapshots`, { method: "POST", body: JSON.stringify({ name }) });
}

export function restoreGraphSnapshot(caseId: string, snapshotId: string): Promise<GraphWorkspace> {
  return request<GraphWorkspace>(`/graph/${encodeURIComponent(caseId)}/snapshots/${encodeURIComponent(snapshotId)}/restore`, { method: "POST" });
}

export function deleteGraphSnapshot(caseId: string, snapshotId: string): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>(`/graph/${encodeURIComponent(caseId)}/snapshots/${encodeURIComponent(snapshotId)}`, { method: "DELETE" });
}

export function getLocalModelConfiguration(): Promise<LocalModelConfiguration | null> {
  return request<LocalModelConfiguration | null>("/local-models/config");
}

export function saveLocalModelConfiguration(
  configuration: LocalModelConfiguration,
): Promise<LocalModelConfiguration> {
  const payload = { ...configuration };
  delete payload.id;
  delete payload.updated_at;
  return request<LocalModelConfiguration>("/local-models/config", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function detectLocalModelServices(): Promise<{ services: LocalModelServiceProbe[] }> {
  return request<{ services: LocalModelServiceProbe[] }>("/local-models/detect");
}

export function listLocalModels(
  provider: LocalModelProviderId,
  endpoint: string,
): Promise<{ models: LocalModelDescriptor[] }> {
  return request<{ models: LocalModelDescriptor[] }>("/local-models/models", {
    method: "POST",
    body: JSON.stringify({ provider, endpoint }),
  });
}

export function testLocalModel(payload: {
  provider: LocalModelProviderId;
  endpoint: string;
  model: string;
  prompt: string;
  temperature: number;
  max_tokens: number;
  timeout_seconds: number;
}): Promise<{ status: string; reply: string; latency_ms: number }> {
  return request<{ status: string; reply: string; latency_ms: number }>("/local-models/test", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getCaseMonitor(caseId: string): Promise<CaseMonitor> {
  return request<CaseMonitor>(`/operations/cases/${caseId}/monitor`);
}

export function listAuditEvents(caseId?: string, limit = 80): Promise<AuditEvent[]> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (caseId) params.set("case_id", caseId);
  return request<AuditEvent[]>(`/operations/audit?${params.toString()}`);
}

// --- Forensic lab ---
export function importHashSet(payload: {
  set_name: string;
  category: "notable" | "known_good";
  severity: string;
  hashes: string;
}): Promise<HashSetImportResult> {
  return request<HashSetImportResult>("/forensic-core/hashsets/import", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listHashSets(): Promise<HashSetInfo[]> {
  return request<HashSetInfo[]>("/forensic-core/hashsets");
}

export function lookupHash(value: string): Promise<HashLookupResult> {
  return request<HashLookupResult>("/forensic-core/hashsets/lookup", {
    method: "POST",
    body: JSON.stringify({ value }),
  });
}

export function correlateSelector(attrType: string, value: string): Promise<CorrelationQueryResult> {
  const q = new URLSearchParams({ attr_type: attrType, value });
  return request<CorrelationQueryResult>(`/forensic-core/correlate?${q.toString()}`);
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

export function createInterestingRule(payload: {
  name: string;
  severity: string;
  name_contains?: string;
  name_glob?: string;
  extensions?: string[];
  types?: string[];
  min_size?: number | null;
  max_size?: number | null;
  min_entropy?: number | null;
  description?: string;
}): Promise<InterestingRule> {
  return request<InterestingRule>("/forensic-core/interesting-rules", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteInterestingRule(ruleId: string): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>(`/forensic-core/interesting-rules/${ruleId}`, {
    method: "DELETE",
  });
}
