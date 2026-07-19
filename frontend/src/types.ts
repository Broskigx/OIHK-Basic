export type CaseRead = {
  id: string;
  owner_id: string | null;
  organization_id: string | null;
  title: string;
  summary: string;
  legal_basis: string;
  scope_statement: string;
  status: string;
  created_at: string;
  updated_at: string;
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
  value?: string;
  created_at?: string;
  updated_at?: string;
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

export type GraphEntityCreate = {
  case_id: string;
  label: string;
  type: string;
  confidence: number;
  connect_to_id?: string | null;
  relation_label: string;
};

export type GraphRelationshipCreate = {
  case_id: string;
  source_id: string;
  target_id: string;
  label: string;
  confidence: number;
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

export type EntityDossier = {
  entity: GraphNode;
  first_seen: string;
  last_seen: string;
  sources: DossierSource[];
  connections: DossierConnection[];
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

export type ForensicFinding = {
  severity: "info" | "low" | "medium" | "high";
  code: string;
  detail: string;
};

export type ForensicCoreReport = {
  filename: string;
  source_id: string | null;
  stored_sha256: string | null;
  custody_sequence: number | null;
  custody_sealed: boolean;
  hashes: HashResult[];
  file_analysis: FileAnalysis | null;
  metadata: MetadataReport | null;
  text_extraction: TextExtraction | null;
  iocs: IocReport | null;
  yara: YaraReport | null;
  timeline_events: TimelineEvent[];
  errors: string[];
};

export type HashResult = {
  algorithm: string;
  digest: string;
  size_bytes: number;
  elapsed_ms: number;
  target: string;
};

export type FileAnalysis = {
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

export type MetadataReport = {
  format: string;
  fields: MetadataField[];
  raw: Record<string, unknown>;
  errors: string[];
};

export type MetadataField = {
  key: string;
  value: string;
  category: string;
};

export type TextExtraction = {
  format: string;
  text: string;
  char_count: number;
  word_count: number;
  errors: string[];
};

export type IocReport = {
  matches: IocMatch[];
  asn_lookups: Array<Record<string, string>>;
};

export type IocMatch = {
  type: string;
  value: string;
  display: string;
  confidence: number;
  offset: number | null;
  context: string;
};

export type YaraReport = {
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

export type TimelineEvent = {
  event_id: string;
  source_id: string | null;
  title: string;
  event_type: string;
  timestamp: string;
  detail: string;
  metadata: Record<string, unknown>;
};

export type OsintLookupResult = {
  value: string;
  kind: string;
  summary: string;
  findings: OsintFinding[];
  errors: string[];
  entities: unknown[];
  relationships: unknown[];
  source: SourceRead;
};

export type OsintFinding = {
  source: string;
  type: string;
  value: string;
  detail: string;
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
  title: string;
  status: string;
  source_count: number;
  entity_count: number;
  relationship_count: number;
  created_at: string;
  updated_at: string;
};

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

export type HashSetImportResult = {
  set_name: string;
  category: string;
  added: number;
  skipped: number;
  invalid: number;
};

export type HashSetInfo = {
  set_name: string;
  category: string;
  entries: number;
};

export type HashLookupResult = {
  value: string;
  matched: boolean;
  matches: Array<{
    set_name: string;
    category: string;
    severity: string;
    algorithm: string;
    digest: string;
    label: string;
  }>;
};

export type InterestingRule = {
  id: string;
  organization_id: string;
  name: string;
  enabled: boolean;
  severity: string;
  extensions: string[];
  types: string[];
  description: string;
  created_at: string;
};

export type CarveResult = {
  parent_sha256: string;
  count: number;
  artifacts: Array<{
    offset: number;
    size: number;
    carved_type: string;
    label: string;
    sha256: string;
    entropy: number;
    source_id: string | null;
  }>;
};
