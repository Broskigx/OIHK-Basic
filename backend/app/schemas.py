"""Pydantic schemas for OIHK Basic."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl

from app.version import PRODUCT_VERSION


# --- Health ---
class HealthRead(BaseModel):
    status: str
    service: str = "oihk-basic-api"
    version: str = PRODUCT_VERSION


# --- Auth ---
class UserCreate(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    username: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str


class UserRead(BaseModel):
    id: str
    email: str
    username: str
    role: str
    organization_id: str = "default"
    is_active: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


# --- Local Copilot and model servers ---
class LocalModelConfigurationWrite(BaseModel):
    provider: Literal["lmstudio", "ollama", "openai_compatible"]
    endpoint: str = Field(min_length=1, max_length=500)
    model: str = Field(default="", max_length=240)
    context_length: int = Field(default=8192, ge=256, le=2_000_000)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=900, ge=1, le=131_072)
    timeout_seconds: int = Field(default=150, ge=2, le=600)
    streaming: bool = True
    system_prompt: str = Field(default="", max_length=16_000)
    capabilities: list[str] = Field(default_factory=list)
    tools_enabled: list[str] = Field(default_factory=list)
    role_models: dict[str, str] = Field(default_factory=dict)
    fallback_model: str = Field(default="", max_length=240)


class LocalModelConfigurationRead(LocalModelConfigurationWrite):
    id: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class LocalModelProbeRequest(BaseModel):
    provider: Literal["lmstudio", "ollama", "openai_compatible"]
    endpoint: str = Field(min_length=1, max_length=500)


class LocalModelTestRequest(LocalModelProbeRequest):
    model: str = Field(min_length=1, max_length=240)
    prompt: str = Field(default="Respond with: OIHK Basic local model ready", min_length=1, max_length=2000)
    temperature: float = Field(default=0.1, ge=0, le=2)
    max_tokens: int = Field(default=80, ge=1, le=2048)


class GeneralSettings(BaseModel):
    language: Literal["en", "es"] = "en"
    default_start: str = Field(default="dashboard", max_length=40)
    default_case_id: str = Field(default="", max_length=36)
    confirmations: bool = True
    check_updates: bool = True
    update_channel: Literal["alpha", "beta", "stable"] = "alpha"


class AppearanceSettings(BaseModel):
    dark_mode: bool = True
    density: Literal["comfortable", "compact"] = "comfortable"
    text_scale: float = Field(default=1, ge=0.85, le=1.3)
    reduce_motion: bool = False
    restore_layout: bool = True


class StorageSettings(BaseModel):
    data_directory: str = Field(default="", max_length=2000)
    backup_on_exit: bool = False
    retention_days: int = Field(default=0, ge=0, le=36500)


class ToolSettings(BaseModel):
    executable_paths: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    max_file_mb: int = Field(default=250, ge=1, le=4096)


class PrivacySettings(BaseModel):
    telemetry_enabled: bool = False
    public_osint_enabled: bool = True
    redact_logs: bool = True
    log_retention_days: int = Field(default=14, ge=1, le=365)


class PerformanceSettings(BaseModel):
    max_visible_nodes: int = Field(default=2500, ge=100, le=100000)
    worker_enabled: bool = True
    quality: Literal["balanced", "quality", "performance"] = "balanced"
    low_power_mode: bool = False


class ApplicationSettingsWrite(BaseModel):
    onboarding_complete: bool = False
    general: GeneralSettings = Field(default_factory=GeneralSettings)
    appearance: AppearanceSettings = Field(default_factory=AppearanceSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    tools: ToolSettings = Field(default_factory=ToolSettings)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)


class ApplicationSettingsRead(ApplicationSettingsWrite):
    id: str = ""
    schema_version: int = 2
    updated_at: datetime | None = None


class StorageStatusRead(BaseModel):
    data_directory: str
    database_path: str
    storage_path: str
    database_bytes: int
    evidence_bytes: int
    total_bytes: int
    writable: bool


# --- Dashboard ---
class DashboardCountsRead(BaseModel):
    active_investigations: int
    registered_evidence: int
    pending_tasks: int | None = None
    tasks_available: bool = False
    connected_modules: int
    registered_modules: int


class DashboardRecentCaseRead(BaseModel):
    id: str
    title: str
    status: str
    priority: str
    evidence_count: int
    updated_at: datetime | None


class DashboardActivityRead(BaseModel):
    id: str
    kind: Literal["audit", "system_link"]
    action: str
    actor: str
    detail: str
    case_id: str | None = None
    case_title: str | None = None
    module_id: str | None = None
    created_at: datetime


class DashboardModuleRead(BaseModel):
    module_id: str
    product_name: str
    module_version: str
    state: str
    enabled: bool
    last_activity_at: datetime | None = None


class DashboardSummaryRead(BaseModel):
    generated_at: datetime
    counts: DashboardCountsRead
    recent_investigations: list[DashboardRecentCaseRead]
    recent_activity: list[DashboardActivityRead]
    modules: list[DashboardModuleRead]


class LocalModelRuntimeStatusRead(BaseModel):
    configured: bool
    connected: bool
    provider: str = ""
    endpoint: str = ""
    model: str = ""
    model_available: bool = False
    model_count: int = 0
    context_length: int | None = None
    max_tokens: int | None = None
    latency_ms: int | None = None
    error: str = ""


class UpdatePrepareRequest(BaseModel):
    target_version: str = Field(min_length=1, max_length=80, pattern=r"^[0-9A-Za-z.+-]+$")
    channel: Literal["alpha", "beta", "stable"] = "alpha"


class UpdatePrepareRead(BaseModel):
    update_token: str
    backup_path: str
    backup_sha256: str
    schema_version: int
    database_bytes: int


class UpdateRecoveryRead(BaseModel):
    stage: str = ""
    source_version: str = ""
    target_version: str = ""
    backup_path: str = ""
    error_code: str = ""
    updated_at: str = ""
    timeout_seconds: int = Field(default=60, ge=2, le=600)


class ConversationCreate(BaseModel):
    case_id: str | None = None
    title: str = Field(default="New conversation", min_length=1, max_length=160)
    model: str = Field(default="", max_length=240)
    settings: dict[str, Any] = Field(default_factory=dict)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    archived: bool | None = None
    model: str | None = Field(default=None, max_length=240)
    settings: dict[str, Any] | None = None


class ConversationRead(BaseModel):
    id: str
    case_id: str | None
    title: str
    archived: bool
    model: str = ""
    settings: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class ConversationMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=16_000)


class ConversationMessageRead(BaseModel):
    id: str
    conversation_id: str
    case_id: str | None
    role: Literal["user", "assistant"]
    content: str
    provider: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationReply(BaseModel):
    user_message: ConversationMessageRead
    assistant_message: ConversationMessageRead


# --- Cases ---
class CaseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    summary: str = ""
    legal_basis: str = Field(min_length=3, max_length=120)
    scope_statement: str = Field(min_length=12)
    priority: Literal["low", "normal", "high", "critical"] = "normal"
    tags: list[str] = Field(default_factory=list, max_length=30)
    notes: str = Field(default="", max_length=50_000)


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    summary: str | None = Field(default=None, max_length=20_000)
    legal_basis: str | None = Field(default=None, min_length=3, max_length=120)
    scope_statement: str | None = Field(default=None, min_length=12, max_length=20_000)
    status: Literal["active", "paused", "closed", "archived"] | None = None
    priority: Literal["low", "normal", "high", "critical"] | None = None
    tags: list[str] | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=50_000)
    graph_config: dict[str, Any] | None = None


class CaseRead(BaseModel):
    id: str
    owner_id: str | None = None
    organization_id: str | None = None
    title: str
    summary: str
    legal_basis: str
    scope_statement: str
    status: str
    priority: str = "normal"
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    graph_config: dict[str, Any] = Field(default_factory=dict)
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    entity_count: int = 0
    relationship_count: int = 0
    source_count: int = 0
    conversation_count: int = 0
    query_count: int = 0

    model_config = {"from_attributes": True}


class CaseImportSource(BaseModel):
    id: str = Field(max_length=80)
    title: str = Field(min_length=1, max_length=240)
    kind: str = Field(min_length=1, max_length=40)
    body: str = Field(default="", max_length=250_000)
    citation: str = Field(default="", max_length=4000)
    license: str = Field(default="unknown", max_length=120)
    reliability: float = Field(default=0.5, ge=0, le=1)


class CaseImportEntity(BaseModel):
    id: str = Field(max_length=80)
    type: str = Field(min_length=1, max_length=40)
    value: str = Field(min_length=1, max_length=500)
    display: str = Field(min_length=1, max_length=500)
    confidence: float = Field(default=0.5, ge=0, le=1)
    source_ids: list[str] = Field(default_factory=list, max_length=1000)
    properties: dict[str, Any] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=50_000)


class CaseImportRelationship(BaseModel):
    subject_id: str = Field(max_length=80)
    predicate: str = Field(min_length=1, max_length=80)
    object_id: str = Field(max_length=80)
    confidence: float = Field(default=0.5, ge=0, le=1)
    source_ids: list[str] = Field(default_factory=list, max_length=1000)


class CaseImportDocument(BaseModel):
    schema_version: int = Field(default=1, ge=1, le=1)
    case: CaseCreate
    sources: list[CaseImportSource] = Field(default_factory=list, max_length=5000)
    entities: list[CaseImportEntity] = Field(default_factory=list, max_length=10000)
    relationships: list[CaseImportRelationship] = Field(default_factory=list, max_length=20000)


# --- Sources ---
class TextIngestRequest(BaseModel):
    case_id: str
    title: str = Field(min_length=3, max_length=240)
    body: str = Field(min_length=3, max_length=250_000)
    citation: str = ""
    license: str = "unknown"
    reliability: float = Field(default=0.5, ge=0, le=1)


class UrlIngestRequest(BaseModel):
    case_id: str
    url: HttpUrl
    title: str | None = Field(default=None, max_length=240)
    license: str = "public-web"
    reliability: float = Field(default=0.5, ge=0, le=1)


class SourceRead(BaseModel):
    id: str
    case_id: str
    title: str
    kind: str
    url: str | None
    citation: str
    license: str
    reliability: float
    robot_compliant: bool
    collected_at: datetime

    model_config = {"from_attributes": True}


class EvidenceItemRead(BaseModel):
    id: str
    case_id: str
    source_id: str
    original_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    notes: str
    tags: list[str]
    entity_ids: list[str]
    ingested_by: str
    original_reference: str
    export_count: int
    created_at: datetime
    updated_at: datetime
    verified_at: datetime | None

    model_config = {"from_attributes": True}


class EvidenceItemUpdate(BaseModel):
    notes: str | None = Field(default=None, max_length=50_000)
    tags: list[str] | None = Field(default=None, max_length=100)
    entity_ids: list[str] | None = Field(default=None, max_length=1000)


class EvidenceVerifyRead(BaseModel):
    id: str
    expected_sha256: str
    actual_sha256: str
    intact: bool
    verified_at: datetime


ReportSection = Literal[
    "investigation",
    "summary",
    "entities",
    "relationships",
    "sources",
    "evidence",
    "notes",
    "timeline",
    "methodology",
    "limitations",
]


class ReportGenerateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    format: Literal["markdown", "html", "json"] = "markdown"
    sections: list[ReportSection] = Field(min_length=1, max_length=10)
    methodology: str = Field(default="", max_length=50_000)
    limitations: str = Field(default="", max_length=50_000)


class ReportDocumentRead(BaseModel):
    id: str
    case_id: str
    title: str
    format: str
    sections: list[str]
    content: str
    status: str
    ai_generated: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReportTemplateWrite(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    format: Literal["markdown", "html", "json"] = "markdown"
    sections: list[ReportSection] = Field(min_length=1, max_length=10)
    methodology: str = Field(default="", max_length=50_000)
    limitations: str = Field(default="", max_length=50_000)


class ReportTemplateRead(ReportTemplateWrite):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReportAiDraftRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    focus: str = Field(default="", max_length=4000)


# --- Entities & Graph ---
class EntityRead(BaseModel):
    id: str
    case_id: str
    type: str
    value: str
    display: str
    confidence: float
    source_ids: list[str]
    first_seen: datetime
    last_seen: datetime

    model_config = {"from_attributes": True}


class RelationshipRead(BaseModel):
    id: str
    case_id: str
    subject_id: str
    predicate: str
    object_id: str
    confidence: float
    source_ids: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestResult(BaseModel):
    source: SourceRead
    entities: list[EntityRead]
    relationships: list[RelationshipRead]


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    confidence: float
    source_ids: list[str]
    value: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    properties: dict = {}
    notes: str = ""


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str
    confidence: float
    source_ids: list[str]


class GraphRead(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphPosition(BaseModel):
    x: float = Field(ge=-1_000_000, le=1_000_000)
    y: float = Field(ge=-1_000_000, le=1_000_000)
    pinned: bool = False


class GraphCamera(BaseModel):
    x: float = Field(default=0, ge=-1_000_000, le=1_000_000)
    y: float = Field(default=0, ge=-1_000_000, le=1_000_000)
    zoom: float = Field(default=1, ge=0.1, le=4)


class GraphWorkspaceWrite(BaseModel):
    positions: dict[str, GraphPosition] = Field(default_factory=dict, max_length=100_000)
    camera: GraphCamera = Field(default_factory=GraphCamera)
    view_mode: Literal["network", "hierarchy", "connections"] = "network"
    filters: dict[str, str] = Field(default_factory=dict, max_length=100)


class GraphWorkspaceRead(GraphWorkspaceWrite):
    id: str = ""
    case_id: str
    updated_at: datetime | None = None


class GraphSnapshotCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class GraphSnapshotRead(BaseModel):
    id: str
    case_id: str
    name: str
    workspace: GraphWorkspaceWrite
    graph_digest: str
    node_count: int
    edge_count: int
    created_at: datetime


class GraphEntityCreate(BaseModel):
    case_id: str
    label: str = Field(min_length=1, max_length=500)
    type: str = Field(default="note", min_length=2, max_length=40)
    confidence: float = Field(default=0.68, ge=0, le=1)
    connect_to_id: str | None = None
    relation_label: str = Field(default="analyst_linked", min_length=2, max_length=80)


class GraphRelationshipCreate(BaseModel):
    case_id: str
    source_id: str
    target_id: str
    label: str = Field(min_length=2, max_length=80)
    confidence: float = Field(default=0.68, ge=0, le=1)


class GraphRelationshipUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=2, max_length=80)
    confidence: float | None = Field(default=None, ge=0, le=1)


class GraphExpandResult(BaseModel):
    entity_id: str
    strategy: str
    summary: str
    new_nodes: list[GraphNode]
    new_edges: list[GraphEdge]
    transform: str | None = None


class EntityLabelUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=500)


class EntityDetailUpdate(BaseModel):
    properties: dict[str, str] | None = None
    notes: str | None = None
    type: str | None = None


class EntityDossier(BaseModel):
    entity: GraphNode
    first_seen: datetime
    last_seen: datetime
    sources: list["DossierSource"]
    connections: list["DossierConnection"]


class DossierSource(BaseModel):
    source_id: str
    title: str
    kind: str
    url: str | None
    citation: str
    reliability: float
    excerpt: str


class DossierConnection(BaseModel):
    relationship_id: str
    relation: str
    direction: Literal["outgoing", "incoming"]
    confidence: float
    entity: GraphNode


# --- Graph Analytics ---
class GraphHubRead(BaseModel):
    entity_id: str
    label: str
    type: str
    degree: int
    score: float


class GraphComponentRead(BaseModel):
    index: int
    size: int
    sample_node_ids: list[str]


class GraphBridgeRead(BaseModel):
    source_id: str
    target_id: str
    label: str


class GraphAnalyticsRead(BaseModel):
    node_count: int
    edge_count: int
    density: float
    component_count: int
    largest_component_size: int
    isolated_node_count: int
    average_degree: float
    type_counts: dict[str, int]
    relation_counts: dict[str, int]
    top_hubs: list[GraphHubRead]
    components: list[GraphComponentRead]
    bridges: list[GraphBridgeRead]


# --- Targets ---
class TargetProfileRead(BaseModel):
    id: str
    case_id: str
    first_name: str
    last_name: str
    aliases: list[str]
    notes: str
    consent_basis: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TargetPhotoRead(BaseModel):
    id: str
    case_id: str
    target_id: str
    source_id: str | None
    filename: str
    content_type: str
    sha256: str
    size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseMemoryRead(BaseModel):
    id: str
    case_id: str
    target_id: str | None
    kind: str
    content: str
    confidence: float
    source_ids: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchRunRead(BaseModel):
    id: str
    case_id: str
    target_id: str
    status: str
    provider: str
    queries: list[str]
    query_count: int
    hit_count: int
    error: str
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class SearchHitRead(BaseModel):
    id: str
    run_id: str
    case_id: str
    target_id: str
    title: str
    url: str
    snippet: str
    rank: int
    source_name: str
    confidence: float
    ingested_source_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TargetIntakeResult(BaseModel):
    case: CaseRead
    target: TargetProfileRead
    photos: list[TargetPhotoRead] = []
    memory: list[CaseMemoryRead] = []
    search_run: SearchRunRead | None = None
    hits: list[SearchHitRead] = []


class AutoInvestigateRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    aliases: str = ""
    notes: str = ""
    legal_basis: str = "Authorized research"
    scope_statement: str = "Bounded authorized OSINT review using user-provided and public sources."
    consent_basis: str = "User confirms authorization to investigate this target."


class AutoInvestigateResult(BaseModel):
    case: CaseRead
    target: TargetProfileRead
    memory: list[CaseMemoryRead]
    search_run: SearchRunRead | None
    hits: list[SearchHitRead]
    summary: "CaseSummary"


class CaseSummary(BaseModel):
    case_id: str
    headline: str
    summary: str
    key_findings: list[str]
    risk_notes: list[str]
    provider: str
    entity_count: int
    source_count: int
    confidence: float


# --- Transforms ---
class TransformRunRequest(BaseModel):
    entity_id: str


class MachineCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = ""
    transform_ids: list[str] = Field(min_length=1)
    input_type: str = ""


class MachineRead(BaseModel):
    id: str
    organization_id: str
    name: str
    description: str
    transform_ids: list[str]
    input_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MachineStep(BaseModel):
    transform: str
    strategy: str
    new_nodes: int


class MachineSkip(BaseModel):
    transform: str
    reason: str


class MachineRunResult(BaseModel):
    entity_id: str
    summary: str
    ran: list[MachineStep]
    skipped: list[MachineSkip] = []
    new_nodes: list[GraphNode]
    new_edges: list[GraphEdge]


class MachineAdhocRun(BaseModel):
    transform_ids: list[str] = Field(min_length=1)


class TransformRunRead(BaseModel):
    id: str
    case_id: str
    entity_id: str
    entity_label: str
    entity_type: str
    transform_id: str
    transform_title: str
    status: Literal["completed", "failed"] = "completed"
    new_nodes: int
    new_edges: int
    detail: str
    actor: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- CSV Import ---
class CsvImportRequest(BaseModel):
    csv: str


class CsvImportResult(BaseModel):
    nodes: int
    edges: int
    errors: list[str]


# --- OSINT ---
class OsintLookupRequest(BaseModel):
    case_id: str
    value: str = Field(min_length=2, max_length=500)


class OsintFindingRead(BaseModel):
    source: str
    type: str
    value: str
    detail: str


class OsintLookupResult(BaseModel):
    query_id: str
    value: str
    kind: str
    summary: str
    findings: list[OsintFindingRead]
    errors: list[str]
    entities: list[EntityRead]
    relationships: list[RelationshipRead]
    source: SourceRead | None = None
    promoted: bool = False


class OsintQueryRead(BaseModel):
    id: str
    case_id: str
    value: str
    kind: str
    findings: list[OsintFindingRead]
    errors: list[str]
    promoted: bool
    source_id: str | None
    created_at: datetime
    promoted_at: datetime | None


# --- Forensics ---
class ForensicFindingRead(BaseModel):
    severity: Literal["info", "low", "medium", "high"]
    code: str
    detail: str


class ForensicReportRead(BaseModel):
    filename: str
    size_bytes: int
    sha256: str
    detected_type: str
    detected_label: str
    claimed_type: str
    type_mismatch: bool
    entropy: float
    max_window_entropy: float
    trailing_bytes: int
    embedded_signatures: list[str]
    lsb: dict[str, Any]
    media_metadata: dict[str, Any]
    suspicion_score: float
    verdict: Literal["clean", "suspicious", "high"]
    findings: list[ForensicFindingRead]
    source_id: str | None = None


# --- Forensic Core ---
class HashResultRead(BaseModel):
    algorithm: str
    digest: str
    size_bytes: int
    elapsed_ms: int
    target: str


class FileAnalysisRead(BaseModel):
    filename: str
    size_bytes: int
    extension: str
    mime_type: str
    magic_bytes: str
    detected_type: str
    detected_label: str
    entropy: float
    hashes: dict[str, str]
    timestamps: dict[str, str | None]
    permissions: str | None
    discrepancies: list[str]


class MetadataFieldRead(BaseModel):
    key: str
    value: str
    category: str


class MetadataReportRead(BaseModel):
    format: str
    fields: list[MetadataFieldRead]
    raw: dict[str, Any]
    errors: list[str]


class TextExtractionRead(BaseModel):
    format: str
    text: str
    char_count: int
    word_count: int
    errors: list[str]


class IocMatchRead(BaseModel):
    type: str
    value: str
    display: str
    confidence: float
    offset: int | None = None
    context: str = ""


class IocReportRead(BaseModel):
    matches: list[IocMatchRead]
    asn_lookups: list[dict[str, str]] = []


class TimelineEventRead(BaseModel):
    event_id: str
    source_id: str | None
    title: str
    event_type: str
    timestamp: str
    detail: str
    metadata: dict[str, Any]


class ForensicCoreRead(BaseModel):
    filename: str
    source_id: str | None = None
    stored_sha256: str | None = None
    custody_sequence: int | None = None
    custody_sealed: bool = False
    hashes: list[HashResultRead] = []
    file_analysis: FileAnalysisRead | None = None
    metadata: MetadataReportRead | None = None
    text_extraction: TextExtractionRead | None = None
    iocs: IocReportRead | None = None
    timeline_events: list[TimelineEventRead] = []
    errors: list[str] = []


# --- Hash Sets ---
class HashSetImportRequest(BaseModel):
    set_name: str = Field(min_length=1, max_length=120)
    category: Literal["notable", "known_good"]
    severity: str = Field(default="high", pattern=r"^(info|low|medium|high|critical)$")
    hashes: str = Field(min_length=1)


class HashSetImportResult(BaseModel):
    set_name: str
    category: str
    added: int
    skipped: int
    invalid: int


class HashSetInfoRead(BaseModel):
    set_name: str
    category: str
    entries: int


class HashLookupRequest(BaseModel):
    value: str = Field(min_length=1, max_length=128)


class HashMatchRead(BaseModel):
    set_name: str
    category: str
    severity: str
    algorithm: str
    digest: str
    label: str


class HashLookupResult(BaseModel):
    value: str
    matched: bool
    matches: list[HashMatchRead]


# --- Correlation ---
class CorrelationIndexRequest(BaseModel):
    case_id: str
    attr_type: str = Field(min_length=2, max_length=40)
    value: str = Field(min_length=1, max_length=400)
    source_id: str | None = None


class CorrelationHitRead(BaseModel):
    case_id: str
    case_title: str
    source_id: str | None
    attr_type: str
    attr_value: str
    display: str
    first_seen_at: datetime


class CorrelationSampleRead(BaseModel):
    attr_type: str
    display: str


class CaseOverlapRead(BaseModel):
    case_id: str
    case_title: str
    shared_count: int
    samples: list[CorrelationSampleRead]


class CorrelationQueryResult(BaseModel):
    attr_type: str
    value: str
    count: int
    hits: list[CorrelationHitRead]


# --- Carving ---
class CarvedArtifactRead(BaseModel):
    offset: int
    size: int
    carved_type: str
    label: str
    sha256: str
    entropy: float
    reason: str
    source_id: str | None = None
    hash_matches: int = 0
    correlation_hits: int = 0


class CarveResult(BaseModel):
    parent_sha256: str
    count: int
    artifacts: list[CarvedArtifactRead]


# --- Interesting Files ---
class InterestingRuleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    severity: str = "medium"
    name_contains: str = ""
    name_glob: str = ""
    extensions: list[str] = []
    types: list[str] = []
    min_size: int | None = None
    max_size: int | None = None
    min_entropy: float | None = None
    description: str = ""


class InterestingRuleRead(BaseModel):
    id: str
    organization_id: str
    name: str
    enabled: bool
    severity: str
    name_contains: str
    name_glob: str
    extensions: list[str]
    types: list[str]
    min_size: int | None
    max_size: int | None
    min_entropy: float | None
    description: str
    created_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Custody ---
class SealStatusRead(BaseModel):
    sequence: int
    source_id: str
    source_title: str
    sealed_at_iso: str
    content_sha256: str
    seal_hash: str
    content_ok: bool
    seal_ok: bool
    chain_ok: bool
    signature_ok: bool
    ok: bool


class CustodyReportRead(BaseModel):
    case_id: str
    intact: bool
    sealed_count: int
    first_broken_sequence: int | None
    entries: list[SealStatusRead]
