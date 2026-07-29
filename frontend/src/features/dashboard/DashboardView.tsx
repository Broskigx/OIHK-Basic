import {
  ArrowRight,
  BriefcaseBusiness,
  Boxes,
  FileArchive,
  CircleDot,
  Clock3,
  Cpu,
  Database,
  Network,
  Plus,
  ShieldCheck,
  Target,
  Upload,
  UserPlus,
  Maximize2,
} from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { getLocalModelConfiguration } from "../../api";
import type { AuditEvent, CaseMonitor, CaseRead, GraphAnalytics, GraphNode, GraphRead, SourceRead, StorageStatus } from "../../types";
import type { PlatformArea } from "../../app/navigation";
import { buildDashboardMetrics, dashboardActionLabel } from "./dashboardModel";
import { shortHash } from "../../utils";

const GraphView = lazy(() =>
  import("../../components/GraphView").then((m) => ({ default: m.GraphView })),
);

// ── Helpers ──

function formatTS(value: string | null): string {
  if (!value) return "—";
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
  } catch {
    return value;
  }
}

function relativeTime(value: string): string {
  try {
    const diff = Date.now() - new Date(value).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  } catch {
    return value;
  }
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let amount = value / 1024;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }
  return `${amount.toFixed(amount >= 10 ? 1 : 2)} ${units[index]}`;
}

// ── Skeleton component ──

function SkeletonRow({ count = 3 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="platform-skeleton platform-skeleton-row" />
      ))}
    </>
  );
}

// ── KPI icon map ──
const KPI_ICONS: Record<string, React.ReactNode> = {
  Investigations: <BriefcaseBusiness size={18} />,
  Entities: <Boxes size={18} />,
  Relationships: <Network size={18} />,
  "Evidence sources": <FileArchive size={18} />,
  "Sealed items": <ShieldCheck size={18} />,
};

// ── Panel wrapper ──

function Panel({
  title,
  actions,
  children,
  loading,
  empty,
  emptyTitle,
  emptyDesc,
}: {
  title: string;
  actions?: React.ReactNode;
  children?: React.ReactNode;
  loading?: boolean;
  empty?: boolean;
  emptyTitle?: string;
  emptyDesc?: string;
}) {
  return (
    <div className="platform-panel">
      <div className="platform-panel-header">
        <h3>{title}</h3>
        {actions && <div className="platform-panel-header-actions">{actions}</div>}
      </div>
      <div className="platform-panel-body">
        {loading ? (
          <SkeletonRow count={4} />
        ) : empty ? (
          <div className="platform-empty-state">
            <strong>{emptyTitle || "No data"}</strong>
            <p>{emptyDesc || "Information will appear here when available."}</p>
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  );
}

// ===================================================================
// MAIN DASHBOARD VIEW
// ===================================================================

export function DashboardView({
  cases,
  activeCase,
  monitor,
  auditEvents,
  sources,
  graph,
  graphAnalytics,
  storageStatus,
  selectedNode,
  onSelectNode,
  onNavigate,
  onNewCase,
}: {
  cases: CaseRead[];
  activeCase?: CaseRead;
  monitor: CaseMonitor | null;
  auditEvents: AuditEvent[];
  sources: SourceRead[];
  graph: GraphRead;
  graphAnalytics: GraphAnalytics | null;
  storageStatus: StorageStatus | null;
  selectedNode: GraphNode | null;
  onSelectNode: (node: GraphNode) => void;
  onNavigate: (area: PlatformArea) => void;
  onNewCase: () => void;
}) {
  const metrics = useMemo(() => buildDashboardMetrics(cases.length, monitor), [cases.length, monitor]);
  const isLoading = false; // Simplified: data is available via props
  const [modelConfigured, setModelConfigured] = useState<boolean | null>(null);

  useEffect(() => {
    let active = true;
    getLocalModelConfiguration()
      .then((configuration) => active && setModelConfigured(Boolean(configuration?.model)))
      .catch(() => active && setModelConfigured(false));
    return () => {
      active = false;
    };
  }, []);

  const reviewTasks = useMemo(() => {
    const tasks: Array<{ label: string; area: PlatformArea }> = [];
    if (!monitor?.custody_intact) tasks.push({ label: "Review chain of custody", area: "evidence" });
    if (graph.nodes.length === 0) tasks.push({ label: "Add the first verified entity", area: "entities" });
    if (sources.length === 0) tasks.push({ label: "Import source material", area: "evidence" });
    if (!modelConfigured) tasks.push({ label: "Configure an optional local model", area: "models" });
    if (!activeCase?.notes) tasks.push({ label: "Record investigation notes", area: "investigations" });
    return tasks.slice(0, 5);
  }, [activeCase?.notes, graph.nodes.length, modelConfigured, monitor?.custody_intact, sources.length]);

  // ── Empty state ──
  if (cases.length === 0) {
    return (
      <div className="platform-dashboard">
        <div className="platform-dash-header">
          <div>
            <h1>Dashboard</h1>
            <p>Operational overview of the active investigation. Create a case to begin.</p>
          </div>
        </div>
        <div className="platform-empty-state" style={{ minHeight: 320, border: "1px dashed var(--border-subtle)", borderRadius: "var(--radius-lg)" }}>
          <Target size={32} color="var(--text-muted)" />
          <strong>No investigation cases yet</strong>
          <p>Create a local case to begin organizing entities, evidence, relationships, and analysis.</p>
          <button className="platform-primary-btn" onClick={onNewCase}>
            <Plus size={16} />
            Create case
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="platform-dashboard">
      {/* ── Header ── */}
      <div className="platform-dash-header">
        <div>
          <h1>
            {activeCase?.title || "Dashboard"}
          </h1>
          <p>
            {activeCase
              ? `Operational overview · ${activeCase.status} · Last updated ${formatTS(activeCase.updated_at)}`
              : "Select an investigation to view its intelligence overview."}
          </p>
        </div>
        <div className="platform-dash-header-actions">
          <button className="platform-ghost-btn" onClick={() => onNavigate("graph")}>
            <Network size={14} /> Open Graph
          </button>
          <button className="platform-primary-btn" onClick={onNewCase}>
            <Plus size={16} /> New Case
          </button>
        </div>
      </div>

      {/* ── KPI Strip ── */}
      <div className="platform-kpi-strip">
        {metrics.map((m) => (
          <div key={m.label} className="platform-kpi-card">
            <div className="platform-kpi-top">
              <span className="platform-kpi-label">{m.label}</span>
              <span className="platform-kpi-icon">{KPI_ICONS[m.label] || <CircleDot size={16} />}</span>
            </div>
            <span className="platform-kpi-value">{m.value}</span>
            {m.change && <span className="platform-kpi-change">{m.change}</span>}
          </div>
        ))}
      </div>

      <div className="dashboard-quick-actions" aria-label="Quick actions">
        <button type="button" onClick={onNewCase}><Plus size={15} /><span><strong>New investigation</strong><small>Create an authorized local case</small></span></button>
        <button type="button" onClick={() => onNavigate("investigations")}><Upload size={15} /><span><strong>Import investigation</strong><small>Open versioned JSON import</small></span></button>
        <button type="button" onClick={() => onNavigate("graph")}><UserPlus size={15} /><span><strong>Add entity</strong><small>Record a verified graph node</small></span></button>
        <button type="button" onClick={() => onNavigate("evidence")}><FileArchive size={15} /><span><strong>Import evidence</strong><small>Hash into managed storage</small></span></button>
        <button type="button" onClick={() => onNavigate("models")}><Cpu size={15} /><span><strong>Local model</strong><small>Configure LM Studio or Ollama</small></span></button>
        <button type="button" onClick={() => onNavigate("graph")}><Network size={15} /><span><strong>Open graph</strong><small>Continue visual analysis</small></span></button>
      </div>

      {/* ── Main Layout (65/35) ── */}
      <div className="platform-dash-columns">
        {/* ── Left Column ── */}
        <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
          {/* ── Intelligence Graph ── */}
          <div className="platform-graph-card">
            <div className="platform-graph-card-header">
              <div className="platform-graph-card-header-left">
                <i className="live-dot" />
                <h2>INTELLIGENCE GRAPH</h2>
                <span className="platform-graph-live-badge">
                  <i className="live-dot" /> Live
                </span>
              </div>
              <div className="platform-graph-card-header-actions">
                <button className="platform-icon-btn" title="Fullscreen" onClick={() => onNavigate("graph")}>
                  <Maximize2 size={14} />
                </button>
              </div>
            </div>
            <div className="platform-graph-card-body">
              <Suspense fallback={<div className="platform-empty-state"><strong>Loading graph...</strong></div>}>
                <GraphView
                  graph={graph}
                  viewMode="network"
                  selectedNodeId={selectedNode?.id}
                  compact
                  onSelectNode={onSelectNode}
                  onNodeClick={(node) => onSelectNode(node)}
                  onNodeContextMenu={(node) => onSelectNode(node)}
                />
              </Suspense>
            </div>
            <div className="platform-graph-status">
              <CircleDot size={12} />
              <span>
                <strong>{graph.nodes.length}</strong> entities ·{" "}
                <strong>{graph.edges.length}</strong> relationships
                {graphAnalytics && (
                  <> · <strong>{graphAnalytics.component_count}</strong> components</>
                )}
              </span>
            </div>
          </div>

          {/* ── Evidence Table ── */}
          <Panel
            title="Evidence"
            actions={
              <button className="platform-text-btn" onClick={() => onNavigate("evidence")}>
                View All <ArrowRight size={12} />
              </button>
            }
            loading={isLoading}
            empty={!sources || sources.length === 0}
            emptyTitle="No evidence added"
            emptyDesc="Upload files or add sources to begin building evidence."
          >
            <table className="platform-evidence-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Source ID</th>
                  <th>Added</th>
                </tr>
              </thead>
              <tbody>
                {(sources || []).slice(0, 5).map((s) => (
                  <tr key={s.id}>
                    <td style={{ maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis" }}>{s.title}</td>
                    <td>{s.kind}</td>
                    <td className="hash-cell" title={s.id}>{shortHash(s.id)}</td>
                    <td style={{ whiteSpace: "nowrap" }}>{relativeTime(s.collected_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {monitor && (
              <div className="platform-verify-row">
                <span className={monitor.custody_intact ? "good" : "bad"}>
                  <ShieldCheck size={13} />
                  {monitor.custody_intact ? "Chain of Custody intact" : "Custody review required"}
                </span>
                <span>{monitor.sealed_count} sealed items</span>
              </div>
            )}
          </Panel>

          {/* ── Sources & Transforms ── */}
          <Panel
            title="Sources & Transforms"
            actions={
              <button className="platform-text-btn" onClick={() => onNavigate("tools")}>
                Configure <ArrowRight size={12} />
              </button>
            }
            loading={isLoading}
            empty={false}
            emptyTitle="No sources configured"
            emptyDesc="Add sources to enrich entities with external intelligence."
          >
            <div className="platform-source-row">
              <span className="platform-source-name">DNS Resolution</span>
              <span className="platform-source-status completed">Local</span>
              <span className="platform-source-time">—</span>
            </div>
            <div className="platform-source-row">
              <span className="platform-source-name">RDAP / WHOIS</span>
              <span className="platform-source-status completed">Local</span>
              <span className="platform-source-time">—</span>
            </div>
            <div className="platform-source-row">
              <span className="platform-source-name">Certificate Search</span>
              <span className="platform-source-status completed">Local</span>
              <span className="platform-source-time">—</span>
            </div>
            <div className="platform-source-row">
              <span className="platform-source-name">Hash Analysis</span>
              <span className="platform-source-status completed">Local</span>
              <span className="platform-source-time">—</span>
            </div>
          </Panel>
        </div>

        {/* ── Right Column ── */}
        <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
          {/* ── Case Overview ── */}
          <Panel
            title="Case Overview"
            actions={
              <button className="platform-text-btn" onClick={() => onNavigate("investigations")}>
                Open <ArrowRight size={12} />
              </button>
            }
            loading={isLoading}
            empty={!activeCase}
            emptyTitle="No active case"
            emptyDesc="Select or create an investigation to see its overview."
          >
            {activeCase && (
              <div className="platform-case-overview">
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <h4 className="placo-title">{activeCase.title}</h4>
                  <span className={`placo-badge ${activeCase.status}`}>{activeCase.status}</span>
                </div>
                {activeCase.summary && (
                  <p className="placo-description">{activeCase.summary}</p>
                )}
                <div className="placo-meta">
                  <div className="placo-meta-row">
                    <span>Last Updated</span>
                    <span>{formatTS(activeCase.updated_at)}</span>
                  </div>
                  <div className="placo-meta-row">
                    <span>Evidence Items</span>
                    <span>{monitor?.source_count ?? sources.length}</span>
                  </div>
                  <div className="placo-meta-row">
                    <span>Entities</span>
                    <span>{monitor?.entity_count ?? graph.nodes.length}</span>
                  </div>
                  <div className="placo-meta-row">
                    <span>Sources</span>
                    <span>{sources.length}</span>
                  </div>
                </div>
                {activeCase.legal_basis && (
                  <div className="placo-tags">
                    <span className="placo-tag">{activeCase.legal_basis}</span>
                    {activeCase.scope_statement && (
                      <span className="placo-tag">{activeCase.scope_statement.slice(0, 40)}</span>
                    )}
                  </div>
                )}
              </div>
            )}
          </Panel>

          <Panel title="Recent Investigations" empty={cases.length === 0}>
            <div className="dashboard-recent-cases">
              {[...cases]
                .sort((left, right) => new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime())
                .slice(0, 5)
                .map((item) => (
                  <button type="button" key={item.id} onClick={() => onNavigate("investigations")}>
                    <span><strong>{item.title}</strong><small>{item.status} · {item.priority} priority</small></span>
                    <time>{relativeTime(item.updated_at)}</time>
                  </button>
                ))}
            </div>
          </Panel>

          <Panel title="Readiness & Resources">
            <div className="dashboard-resources">
              <button type="button" onClick={() => onNavigate("models")}>
                <Cpu size={16} />
                <span><strong>Local model</strong><small>{modelConfigured === null ? "Checking local configuration…" : modelConfigured ? "Configured for local inference" : "Optional · not configured"}</small></span>
                <i className={modelConfigured ? "ready" : "optional"} />
              </button>
              <button type="button" onClick={() => onNavigate("settings")}>
                <Database size={16} />
                <span><strong>Local storage</strong><small>{storageStatus ? `${formatBytes(storageStatus.total_bytes)} · ${storageStatus.writable ? "writable" : "read-only"}` : "Checking application storage…"}</small></span>
                <i className={storageStatus?.writable ? "ready" : "review"} />
              </button>
            </div>
            <div className="dashboard-task-list">
              <div><strong>Review queue</strong><span>{reviewTasks.length}</span></div>
              {reviewTasks.length === 0 && <p>Core investigation records are ready for review.</p>}
              {reviewTasks.map((task) => <button type="button" key={task.label} onClick={() => onNavigate(task.area)}><CircleDot size={11} /> {task.label}<ArrowRight size={11} /></button>)}
            </div>
          </Panel>

          {/* ── Timeline ── */}
          <Panel
            title={`Timeline${activeCase ? ` · ${activeCase.title.slice(0, 24)}` : ""}`}
            actions={
              <button className="platform-text-btn" onClick={() => onNavigate("timeline")}>
                View All <ArrowRight size={12} />
              </button>
            }
            loading={isLoading}
            empty={!auditEvents || auditEvents.length === 0}
            emptyTitle="No recent activity"
            emptyDesc="Timeline events will appear as you work on the case."
          >
            <div className="platform-timeline">
              {(auditEvents || []).slice(0, 6).map((evt) => (
                <div key={evt.id} className="platform-timeline-item">
                  <div className="platform-timeline-dot system" />
                  <div className="platform-timeline-content">
                    <strong>{dashboardActionLabel(evt.action)}</strong>
                    <span>{evt.actor}</span>
                    <time>{formatTS(evt.created_at)}</time>
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          {/* ── Recent Activity ── */}
          <Panel
            title="Recent Activity"
            loading={isLoading}
            empty={!auditEvents || auditEvents.length === 0}
            emptyTitle="No recent activity"
            emptyDesc="Actions performed in this case will appear here."
          >
            {(auditEvents || []).slice(0, 4).map((evt) => (
              <div key={evt.id} className="platform-activity-item">
                <div className="platform-activity-icon system">
                  <Clock3 size={13} />
                </div>
                <div className="platform-activity-info">
                  <strong>{dashboardActionLabel(evt.action)}</strong>
                  <span>{evt.actor}</span>
                </div>
                <span className="platform-activity-time">{relativeTime(evt.created_at)}</span>
              </div>
            ))}
          </Panel>
        </div>
      </div>
    </div>
  );
}
