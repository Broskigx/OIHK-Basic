export type CaseRead = {
  id: string;
  owner_id: string | null;
  organization_id: string | null;
  title: string;
  summary: string;
  legal_basis: string;
  scope_statement: string;
  status: string;
  priority: "low" | "normal" | "high" | "critical";
  tags: string[];
  notes: string;
  graph_config: Record<string, unknown>;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
  entity_count: number;
  relationship_count: number;
  source_count: number;
  conversation_count: number;
  query_count: number;
};

export type InvestigationDraft = {
  title: string;
  summary: string;
  legal_basis: string;
  scope_statement: string;
  priority: "low" | "normal" | "high" | "critical";
  tags: string[];
  notes: string;
};

export type ApplicationSettings = {
  id: string;
  schema_version: number;
  onboarding_complete: boolean;
  general: { language: "en" | "es"; default_start: string; default_case_id: string; confirmations: boolean; check_updates: boolean; update_channel: "alpha" | "beta" | "stable" };
  appearance: { dark_mode: boolean; density: "comfortable" | "compact"; text_scale: number; reduce_motion: boolean; restore_layout: boolean };
  storage: { data_directory: string; backup_on_exit: boolean; retention_days: number };
  tools: { executable_paths: Record<string, string>; timeout_seconds: number; max_file_mb: number };
  privacy: { telemetry_enabled: boolean; public_osint_enabled: boolean; redact_logs: boolean; log_retention_days: number };
  performance: { max_visible_nodes: number; worker_enabled: boolean; quality: "balanced" | "quality" | "performance"; low_power_mode: boolean };
  updated_at: string | null;
};

export type StorageStatus = {
  data_directory: string;
  database_path: string;
  storage_path: string;
  database_bytes: number;
  evidence_bytes: number;
  total_bytes: number;
  writable: boolean;
};

export type SourceRead = {
  id: string;
  case_id: string;
  title: string;
  kind: string;
  url: string | null;
  citation: string;
  license: string;
  reliability: number;
  robot_compliant: boolean;
  collected_at: string;
};

export type GraphNode = {
  id: string;
  label: string;
  type: string;
  confidence: number;
  source_ids: string[];
  properties?: Record<string, string>;
  notes?: string;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
  confidence: number;
  source_ids: string[];
};

export type GraphRead = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type GraphHub = {
  entity_id: string;
  label: string;
  type: string;
  degree: number;
  score: number;
};

export type GraphComponent = {
  index: number;
  size: number;
  sample_node_ids: string[];
};

export type GraphBridge = {
  source_id: string;
  target_id: string;
  label: string;
};

export type GraphAnalytics = {
  node_count: number;
  edge_count: number;
  density: number;
  component_count: number;
  largest_component_size: number;
  isolated_node_count: number;
  average_degree: number;
  type_counts: Record<string, number>;
  relation_counts: Record<string, number>;
  top_hubs: GraphHub[];
  components: GraphComponent[];
  bridges: GraphBridge[];
};

export type GraphEntityCreate = {
  case_id: string;
  label: string;
  type: string;
  confidence: number;
  connect_to_id?: string | null;
  relation_label: string;
};

export type IngestResult = {
  source: SourceRead;
  entities: unknown[];
  relationships: unknown[];
};

export type TargetProfile = {
  id: string;
  case_id: string;
  first_name: string;
  last_name: string;
  aliases: string[];
  notes: string;
  consent_basis: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type TargetPhoto = {
  id: string;
  case_id: string;
  target_id: string;
  source_id: string | null;
  filename: string;
  content_type: string;
  sha256: string;
  size_bytes: number;
  created_at: string;
};

export type CaseMemory = {
  id: string;
  case_id: string;
  target_id: string | null;
  kind: string;
  content: string;
  confidence: number;
  source_ids: string[];
  created_at: string;
};

export type SearchRun = {
  id: string;
  case_id: string;
  target_id: string;
  status: string;
  provider: string;
  queries: string[];
  query_count: number;
  hit_count: number;
  error: string;
  created_at: string;
  completed_at: string | null;
};

export type SearchHit = {
  id: string;
  run_id: string;
  case_id: string;
  target_id: string;
  title: string;
  url: string;
  snippet: string;
  rank: number;
  source_name: string;
  confidence: number;
  ingested_source_id: string | null;
  created_at: string;
};

export type TargetIntakeResult = {
  case: CaseRead;
  target: TargetProfile;
  photos: TargetPhoto[];
  memory: CaseMemory[];
  search_run: SearchRun | null;
  hits: SearchHit[];
};

export type AppMode = "ai" | "pro";

export type User = {
  id: string;
  email: string;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
};

export type ToolCall = {
  tool: string;
  arguments: Record<string, unknown>;
  result_summary: string;
  ok: boolean;
};

export type AssistantChatResponse = {
  reply: string;
  provider: string;
  tool_calls: ToolCall[];
  case_id: string | null;
  data_changed: boolean;
};

export type AssistantMessage = {
  id: string;
  case_id: string | null;
  role: "user" | "assistant";
  content: string;
  provider: string;
  tool_calls: ToolCall[];
  created_at: string;
};

export type EvidenceItem = {
  id: string;
  case_id: string;
  source_id: string;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  notes: string;
  tags: string[];
  entity_ids: string[];
  ingested_by: string;
  original_reference: string;
  export_count: number;
  created_at: string;
  updated_at: string;
  verified_at: string | null;
};

export type EvidenceVerification = {
  id: string;
  expected_sha256: string;
  actual_sha256: string;
  intact: boolean;
  verified_at: string;
};

export type ReportSection = "investigation" | "summary" | "entities" | "relationships" | "sources" | "evidence" | "notes" | "timeline" | "methodology" | "limitations";

export type ReportDocument = {
  id: string;
  case_id: string;
  title: string;
  format: "markdown" | "html" | "json";
  sections: ReportSection[];
  content: string;
  status: "draft" | "approved";
  ai_generated: boolean;
  created_at: string;
  updated_at: string;
};

export type ReportTemplate = {
  id: string;
  name: string;
  format: "markdown" | "html" | "json";
  sections: ReportSection[];
  methodology: string;
  limitations: string;
  created_at: string;
  updated_at: string;
};

export type GraphWorkspace = {
  id?: string;
  case_id?: string;
  positions: Record<string, { x: number; y: number; pinned: boolean }>;
  camera: { x: number; y: number; zoom: number };
  view_mode: "network" | "hierarchy" | "connections";
  filters: Record<string, string>;
  updated_at?: string | null;
};

export type GraphSnapshot = {
  id: string;
  case_id: string;
  name: string;
  workspace: Omit<GraphWorkspace, "id" | "case_id" | "updated_at">;
  graph_digest: string;
  node_count: number;
  edge_count: number;
  created_at: string;
};

export type CopilotConversation = {
  id: string;
  case_id: string | null;
  title: string;
  archived: boolean;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type CopilotMessage = {
  id: string;
  conversation_id: string;
  case_id: string | null;
  role: "user" | "assistant";
  content: string;
  provider: string;
  tool_calls: ToolCall[];
  created_at: string;
};

export type CopilotReply = {
  user_message: CopilotMessage;
  assistant_message: CopilotMessage;
};

export type LocalModelProviderId = "lmstudio" | "ollama" | "openai_compatible";

export type LocalModelDescriptor = {
  id: string;
  name: string;
  context_length?: number | null;
  size_bytes?: number | null;
};

export type LocalModelConfiguration = {
  id?: string;
  provider: LocalModelProviderId;
  endpoint: string;
  model: string;
  context_length: number;
  temperature: number;
  max_tokens: number;
  timeout_seconds: number;
  streaming: boolean;
  system_prompt: string;
  capabilities: string[];
  tools_enabled: string[];
  role_models: Record<string, string>;
  fallback_model: string;
  updated_at?: string;
};

export type LocalModelServiceProbe = {
  provider: LocalModelProviderId;
  endpoint: string;
  status: "online" | "offline";
  models: LocalModelDescriptor[];
  latency_ms: number;
  error: string;
};

export type CaseSummary = {
  case_id: string;
  headline: string;
  summary: string;
  key_findings: string[];
  risk_notes: string[];
  provider: string;
  entity_count: number;
  source_count: number;
  confidence: number;
};

export type AutoInvestigateResult = {
  case: CaseRead;
  target: TargetProfile;
  memory: CaseMemory[];
  search_run: SearchRun | null;
  hits: SearchHit[];
  summary: CaseSummary;
};

export type AutoStreamEvent = {
  phase:
    | "start"
    | "case"
    | "planning"
    | "planned"
    | "searching"
    | "results"
    | "hit"
    | "search_error"
    | "reading"
    | "page"
    | "read_done"
    | "summarizing"
    | "done"
    | "error";
  step?: "case" | "plan" | "search" | "ingest" | "read" | "summary" | "done" | "error";
  label?: string;
  progress?: number;
  case_id?: string;
  target_id?: string;
  provider?: string;
  queries?: string[];
  url?: string;
  index?: number;
  total?: number;
  source_name?: string;
  entities?: { label: string; type: string }[];
  entity_total?: number;
  hit_count?: number;
  summary?: CaseSummary;
  message?: string;
};

export type GraphExpandResult = {
  entity_id: string;
  strategy: string;
  summary: string;
  new_nodes: GraphNode[];
  new_edges: GraphEdge[];
  transform?: string | null;
};

export type TransformSpec = {
  id: string;
  title: string;
  input_types: string[];
  output_types: string[];
  category: string;
  cost: string;
  requires: string[];
  keyless: boolean;
  enabled: boolean;
  description: string;
};

export type TransformCatalog = {
  count: number;
  categories: string[];
  transforms: TransformSpec[];
};

export type CsvImportResult = {
  nodes: number;
  edges: number;
  errors: string[];
};

export type MachineSpec = {
  id: string;
  organization_id: string;
  name: string;
  description: string;
  transform_ids: string[];
  input_type: string;
  created_at: string;
};

export type MachineRunResult = {
  entity_id: string;
  summary: string;
  ran: { transform: string; strategy: string; new_nodes: number }[];
  skipped: { transform: string; reason: string }[];
  new_nodes: GraphNode[];
  new_edges: GraphEdge[];
};

export type DossierSource = {
  source_id: string;
  title: string;
  kind: string;
  url: string | null;
  citation: string;
  reliability: number;
  excerpt: string;
};

export type DossierConnection = {
  relationship_id: string;
  relation: string;
  direction: "outgoing" | "incoming";
  confidence: number;
  entity: GraphNode;
};

export type EntityDossier = {
  entity: GraphNode;
  first_seen: string;
  last_seen: string;
  sources: DossierSource[];
  connections: DossierConnection[];
};

export type SealStatus = {
  sequence: number;
  source_id: string;
  source_title: string;
  sealed_at_iso: string;
  content_sha256: string;
  seal_hash: string;
  content_ok: boolean;
  seal_ok: boolean;
  chain_ok: boolean;
  signature_ok: boolean;
  ok: boolean;
};

export type CustodyReport = {
  case_id: string;
  intact: boolean;
  sealed_count: number;
  first_broken_sequence: number | null;
  entries: SealStatus[];
};

export type ForensicFinding = {
  severity: "info" | "low" | "medium" | "high";
  code: string;
  detail: string;
};

export type ForensicReport = {
  filename: string;
  size_bytes: number;
  sha256: string;
  detected_type: string;
  detected_label: string;
  claimed_type: string;
  type_mismatch: boolean;
  entropy: number;
  max_window_entropy: number;
  trailing_bytes: number;
  embedded_signatures: string[];
  lsb: Record<string, unknown>;
  media_metadata: Record<string, unknown>;
  suspicion_score: number;
  verdict: "clean" | "suspicious" | "high";
  findings: ForensicFinding[];
  source_id: string | null;
};

export type ForensicHashResult = {
  algorithm: string;
  digest: string;
  size_bytes: number;
  elapsed_ms: number;
  target: string;
};

export type ForensicFileAnalysis = {
  filename: string;
  size_bytes: number;
  extension: string;
  mime_type: string;
  magic_bytes: string;
  detected_type: string;
  detected_label: string;
  entropy: number;
  hashes: Record<string, string>;
  timestamps: Record<string, string | null>;
  permissions: string | null;
  discrepancies: string[];
};

export type ForensicMetadataField = {
  key: string;
  value: string;
  category: string;
};

export type ForensicMetadataReport = {
  format: string;
  fields: ForensicMetadataField[];
  raw: Record<string, unknown>;
  errors: string[];
};

export type ForensicTextExtraction = {
  format: string;
  text: string;
  char_count: number;
  word_count: number;
  errors: string[];
};

export type ForensicIocMatch = {
  type: string;
  value: string;
  display: string;
  confidence: number;
  offset: number | null;
  context: string;
};

export type ForensicTimelineEvent = {
  event_id: string;
  source_id: string | null;
  title: string;
  event_type: string;
  timestamp: string;
  detail: string;
  metadata: Record<string, unknown>;
};

export type ForensicYaraReport = {
  matches: Array<{
    rule: string;
    namespace: string;
    tags: string[];
    strings: string[];
    meta: Record<string, string>;
  }>;
  rules_loaded: number;
  available: boolean;
  error: string | null;
};

export type ForensicCoreReport = {
  filename: string;
  source_id: string | null;
  stored_sha256: string | null;
  custody_sequence: number | null;
  custody_sealed: boolean;
  hashes: ForensicHashResult[];
  file_analysis: ForensicFileAnalysis | null;
  metadata: ForensicMetadataReport | null;
  text_extraction: ForensicTextExtraction | null;
  iocs: { matches: ForensicIocMatch[]; asn_lookups: Array<Record<string, string>> } | null;
  yara: ForensicYaraReport | null;
  timeline_events: ForensicTimelineEvent[];
  errors: string[];
};

export type OsintFinding = {
  source: string;
  type: string;
  value: string;
  detail: string;
};

export type OsintLookupResult = {
  query_id: string;
  value: string;
  kind: string;
  summary: string;
  findings: OsintFinding[];
  errors: string[];
  entities: unknown[];
  relationships: unknown[];
  source: SourceRead | null;
  promoted: boolean;
};

export type OsintQuery = {
  id: string;
  case_id: string;
  value: string;
  kind: string;
  findings: OsintFinding[];
  errors: string[];
  promoted: boolean;
  source_id: string | null;
  created_at: string;
  promoted_at: string | null;
};

export type Provider = {
  id: string;
  name: string;
  category: string;
  access: string;
  auth: string;
  connector_type: string;
  capabilities: string[];
  env_var: string;
  configured: boolean;
  status: "catalogued" | "configured" | "verified" | "operational" | "error";
};

export type ProviderCatalog = {
  total: number;
  connected: number;
  operational: number;
  configured: number;
  catalogued: number;
  keyless: number;
  requires_configuration: number;
  categories: Record<string, number>;
  providers: Provider[];
};

export type AuditEvent = {
  id: number;
  actor: string;
  action: string;
  case_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
};

export type CaseMonitor = {
  case_id: string;
  generated_at: string;
  status: string;
  source_count: number;
  entity_count: number;
  relationship_count: number;
  sealed_count: number;
  custody_intact: boolean;
  active_search_runs: number;
  latest_activity_at: string | null;
  source_mix: Record<string, number>;
  risk_flags: string[];
  recent_events: AuditEvent[];
};

// --- UI form state shared between App and its view components ---

export type IntakeForm = {
  first_name: string;
  last_name: string;
  aliases: string;
  notes: string;
  legal_basis: string;
  scope_statement: string;
  consent_basis: string;
  auto_search: boolean;
  photos: File[];
};

export type SourceForm = {
  mode: string;
  title: string;
  body: string;
  url: string;
  citation: string;
  license: string;
  reliability: number;
};

export type ManualEntityForm = {
  label: string;
  type: string;
  confidence: number;
  relation_label: string;
};

// Streaming agent investigation events (POST /assistant/investigate/stream)
export type InvestigateEvent =
  | { type: "status"; phase?: string; text: string }
  | { type: "thought"; text: string }
  | { type: "tool"; tool: string; args?: unknown; status: "running" | "done"; ok?: boolean; summary?: string }
  | { type: "finding"; text: string; confidence?: number }
  | {
      type: "graph";
      label: string;
      node_type: string;
      description?: string;
      relation?: string;
      confidence?: number;
      case_id?: string;
    }
  | { type: "final"; reply: string; provider?: string; case_id?: string | null; data_changed?: boolean }
  | { type: "error"; message: string };

export type DesktopStatus = {
  mode: string;
  product: string;
  version: string;
  platform: string;
  api_endpoint: string;
  backend_managed?: boolean;
  updater_enabled?: boolean;
  recovery?: DesktopRecoveryStatus | null;
};

export type DesktopRecoveryStatus = {
  stage: string;
  source_version: string;
  target_version: string;
  backup_path: string;
  error_code: string;
  updated_at: string;
};

// --- Forensic lab (hash sets, correlation, carving, interesting files) ---
export interface HashSetImportResult {
  set_name: string;
  category: string;
  added: number;
  skipped: number;
  invalid: number;
}

export interface HashSetInfo {
  set_name: string;
  category: string;
  entries: number;
}

export interface HashMatch {
  set_name: string;
  category: string;
  severity: string;
  algorithm: string;
  digest: string;
  label: string;
}

export interface HashLookupResult {
  value: string;
  matched: boolean;
  matches: HashMatch[];
}

export interface CorrelationHit {
  case_id: string;
  case_title: string;
  source_id: string | null;
  attr_type: string;
  attr_value: string;
  display: string;
  first_seen_at: string;
}

export interface CorrelationQueryResult {
  attr_type: string;
  value: string;
  count: number;
  hits: CorrelationHit[];
}

export interface CarvedArtifact {
  offset: number;
  size: number;
  carved_type: string;
  label: string;
  sha256: string;
  entropy: number;
  reason: string;
  source_id: string;
  hash_matches: number;
  correlation_hits: number;
}

export interface CarveResult {
  parent_sha256: string;
  count: number;
  artifacts: CarvedArtifact[];
}

export interface InterestingRule {
  id: string;
  organization_id: string;
  name: string;
  enabled: boolean;
  severity: string;
  name_contains: string;
  name_glob: string;
  extensions: string[];
  types: string[];
  min_size: number | null;
  max_size: number | null;
  min_entropy: number | null;
  description: string;
}
