"""Pydantic schemas for OIHK Basic."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


# --- Health ---
class HealthRead(BaseModel):
    status: str
    service: str = "oihk-basic-api"
    version: str = "0.1.0"


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


# --- Cases ---
class CaseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    summary: str = ""
    legal_basis: str = Field(min_length=3, max_length=120)
    scope_statement: str = Field(min_length=12)


class CaseRead(BaseModel):
    id: str
    owner_id: str | None = None
    organization_id: str | None = None
    title: str
    summary: str
    legal_basis: str
    scope_statement: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


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
    value: str
    kind: str
    summary: str
    findings: list[OsintFindingRead]
    errors: list[str]
    entities: list[EntityRead]
    relationships: list[RelationshipRead]
    source: SourceRead


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


class YaraMatchRead(BaseModel):
    rule: str
    namespace: str
    tags: list[str]
    strings: list[str]
    meta: dict[str, str]


class YaraScanRead(BaseModel):
    matches: list[YaraMatchRead]
    rules_loaded: int
    available: bool
    error: str | None


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
    yara: YaraScanRead | None = None
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
