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

export type DashboardSummary = {
  generated_at: string;
  counts: {
    active_investigations: number;
    registered_evidence: number;
    pending_tasks: number | null;
    tasks_available: boolean;
    connected_modules: number;
    registered_modules: number;
  };
  recent_investigations: Array<{
    id: string;
    title: string;
    status: string;
    priority: string;
    evidence_count: number;
    updated_at: string | null;
  }>;
  recent_activity: Array<{
    id: string;
    kind: "audit" | "system_link";
    action: string;
    actor: string;
    detail: string;
    case_id: string | null;
    case_title: string | null;
    module_id: string | null;
    created_at: string;
  }>;
  modules: Array<{
    module_id: string;
    product_name: string;
    module_version: string;
    state: string;
    enabled: boolean;
    last_activity_at: string | null;
  }>;
};

export type LocalModelRuntimeStatus = {
  configured: boolean;
  connected: boolean;
  provider: string;
  endpoint: string;
  model: string;
  model_available: boolean;
  model_count: number;
  context_length: number | null;
  max_tokens: number | null;
  latency_ms: number | null;
  error: string;
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
  value?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
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

type GraphHub = {
  entity_id: string;
  label: string;
  type: string;
  degree: number;
  score: number;
};

type GraphComponent = {
  index: number;
  size: number;
  sample_node_ids: string[];
};

type GraphBridge = {
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

type ToolCall = {
  tool: string;
  arguments: Record<string, unknown>;
  result_summary: string;
  ok: boolean;
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
  /** True when Basic holds the bytes; false when it only records a linked module's exhibit. */
  held_by_basic: boolean;
  export_count: number;
  created_at: string;
  updated_at: string;
  verified_at: string | null;
  /** Verdict of the last check: null when no check is on record. */
  last_verification_intact: boolean | null;
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
  model: string;
  settings: Record<string, unknown>;
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

type DossierSource = {
  source_id: string;
  title: string;
  kind: string;
  url: string | null;
  citation: string;
  reliability: number;
  excerpt: string;
};

type DossierConnection = {
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

type SealStatus = {
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

type OsintFinding = {
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

type Provider = {
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

export type ManualEntityForm = {
  label: string;
  type: string;
  confidence: number;
  relation_label: string;
};

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

