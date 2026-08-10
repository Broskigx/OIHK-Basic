import {
  ArrowRight,
  Bot,
  Boxes,
  BriefcaseBusiness,
  CircleDot,
  FileArchive,
  Network,
  Plus,
  Search,
  ShieldCheck,
  Target,
  Activity,
  AlertTriangle,
  MessageSquare,
  Lightbulb,
} from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { getLocalModelConfiguration, listTransformRuns } from "../../api";
import type {
  AuditEvent,
  CaseMonitor,
  CaseRead,
  GraphAnalytics,
  GraphNode,
  GraphRead,
  SourceRead,
  StorageStatus,
  TransformRun,
} from "../../types";
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



// ── KPI icon map ──
const KPI_ICONS: Record<string, React.ReactNode> = {
  Investigations: <BriefcaseBusiness size={15} />,
  Entities: <Boxes size={15} />,
  Relationships: <Network size={15} />,
  "Evidence sources": <FileArchive size={15} />,
  "Sealed items": <ShieldCheck size={15} />,
  "Custody Status": <ShieldCheck size={15} />,
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
          <div className="platform-skeleton-strip">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="platform-skeleton platform-skeleton-row" />
            ))}
          </div>
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
  const metrics = useMemo(
    () => buildDashboardMetrics({ investigations: cases.length, graph, sources, monitor }),
    [cases.length, graph, sources, monitor],
  );
  const [modelConfigured, setModelConfigured] = useState<boolean | null>(null);
  const [transformRuns, setTransformRuns] = useState<TransformRun[]>([]);
  const [transformRunsLoading, setTransformRunsLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getLocalModelConfiguration()
      .then((configuration) => active && setModelConfigured(Boolean(configuration?.model)))
      .catch(() => active && setModelConfigured(false));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setTransformRunsLoading(true);
    listTransformRuns(activeCase?.id, 15)
      .then((runs) => active && setTransformRuns(runs))
      .catch(() => active && setTransformRuns([]))
      .finally(() => active && setTransformRunsLoading(false));
    return () => { active = false; };
  }, [activeCase?.id]);

  const reviewTasks = useMemo(() => {
    const tasks: Array<{ label: string; area: PlatformArea; priority: "high" | "medium" | "low" }> = [];
    if (monitor && !monitor.custody_intact) tasks.push({ label: "Custody verification required", area: "evidence", priority: "high" });
    if (!activeCase?.scope_statement) tasks.push({ label: "Missing case scope", area: "investigations", priority: "medium" });
    if (!modelConfigured) tasks.push({ label: "Local model not configured", area: "models", priority: "low" });
    if (graph.nodes.length > 0 && graph.nodes.some((n) => n.source_ids.length === 0)) tasks.push({ label: "Entities without sources", area: "graph", priority: "medium" });
    if (sources.length > 0 && !monitor) tasks.push({ label: "Evidence awaiting review", area: "evidence", priority: "medium" });
    return tasks.slice(0, 6);
  }, [activeCase?.scope_statement, graph.nodes, modelConfigured, monitor, sources]);

  // Recent activity data
  const recentActivities = useMemo(() => {
    const items: Array<{ icon: React.ReactNode; action: string; time: string; actor: string }> = [];
    if (auditEvents) {
      for (const evt of auditEvents.slice(0, 8)) {
        items.push({
          icon: <Activity size={12} />,
          action: dashboardActionLabel(evt.action),
          time: relativeTime(evt.created_at),
          actor: evt.actor,
        });
      }
    }
    if (items.length === 0 && activeCase) {
      items.push({
        icon: <BriefcaseBusiness size={12} />,
        action: "Case created",
        time: relativeTime(activeCase.created_at),
        actor: "System",
      });
    }
    return items;
  }, [auditEvents, activeCase]);

  const evidenceItems = useMemo(() => sources.slice(0, 5), [sources]);

  // Evidence integrity status using monitor data
  const getEvidenceIntegrity = (): string => {
    if (monitor?.custody_intact === false) return "Pending review";
    return "Verified";
  };

  const getEvidenceStatus = (source: SourceRead): string => {
    if (!source.url) return "Missing source";
    return "Present";
  };

  // Tools & Sources status
  const recentRuns = useMemo(() => transformRuns.slice(0, 12), [transformRuns]);

  // ── Empty state ──
  if (cases.length === 0) {
    return (
      <div className="platform-dashboard">
        {/* Level 1: Header */}
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
      {/* ════════════════════════════════════════════ */}
      {/* LEVEL 1: Case Header                        */}
      {/* ════════════════════════════════════════════ */}
      <div className="platform-dash-header">
        <div className="platform-dash-header-left">
          <h1>{activeCase?.title || "Dashboard"}</h1>
          <div className="platform-dash-header-meta">
            {activeCase && (
              <>
                <span className={`placo-badge ${activeCase.status}`}>{activeCase.status}</span>
                <span className="platform-dash-header-date">Last updated {formatTS(activeCase.updated_at)}</span>
              </>
            )}
            {activeCase?.summary && <p className="platform-dash-header-desc">{activeCase.summary}</p>}
          </div>
        </div>
        <div className="platform-dash-header-actions">
          <button className="platform-ghost-btn" onClick={() => onNavigate("graph")}>
            <Network size={14} /> Open Graph
          </button>
          <button className="platform-primary-btn" onClick={onNewCase}>
            <Plus size={16} /> New Investigation
          </button>
        </div>
      </div>

      {/* ════════════════════════════════════════════ */}
      {/* LEVEL 2: Compact Metrics Strip              */}
      {/* ════════════════════════════════════════════ */}
      <div className="platform-kpi-strip">
        {metrics.map((m) => (
          <div key={m.label} className="platform-kpi-card">
            <div className="platform-kpi-top">
              <span className="platform-kpi-label">{m.label}</span>
              <span className="platform-kpi-icon">{KPI_ICONS[m.label] || <CircleDot size={14} />}</span>
            </div>
            <span className="platform-kpi-value">{m.value}</span>
          </div>
        ))}
        <div className="platform-kpi-card">
          <div className="platform-kpi-top">
            <span className="platform-kpi-label">Custody Status</span>
            <span className="platform-kpi-icon"><ShieldCheck size={14} /></span>
          </div>
          <span className="platform-kpi-value" style={{ fontSize: 14, fontWeight: 600 }}>
            {monitor ? (monitor.custody_intact ? "Verified" : "Review") : "—"}
          </span>
        </div>
      </div>

      {/* ════════════════════════════════════════════ */}
      {/* LEVEL 3: Main Area (68% / 32%)              */}
      {/* ════════════════════════════════════════════ */}
      <div className="platform-dash-main">
        {/* ── Left: Intelligence Graph ── */}
        <div className="platform-dash-graph-col">
          <div className="platform-graph-card">
            <div className="platform-graph-card-header">
              <div className="platform-graph-card-header-left">
                <i className="live-dot" />
                <h2>INTELLIGENCE GRAPH</h2>
              </div>
              <div className="platform-graph-card-header-actions">
                <button className="platform-icon-btn" title="Fullscreen" onClick={() => onNavigate("graph")}>
                  <ArrowRight size={14} />
                </button>
              </div>
            </div>
            <div className="platform-graph-card-body">
              {graph.nodes.length === 0 ? (
                <div className="platform-empty-state" style={{ minHeight: 400 }}>
                  <Network size={28} color="var(--text-muted)" />
                  <strong>Graph is empty</strong>
                  <p>Add an entity to start building intelligence relationships.</p>
                  <button className="platform-ghost-btn" onClick={() => onNavigate("entities")}>
                    <Plus size={14} /> Add entity
                  </button>
                </div>
              ) : (
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
              )}
            </div>
            <div className="platform-graph-status">
              <CircleDot size={10} />
              <span>
                <strong>{graph.nodes.length}</strong> entities ·
                <strong>{graph.edges.length}</strong> relationships
                {graphAnalytics && (
                  <> · <strong>{graphAnalytics.component_count}</strong> components</>
                )}
              </span>
              {graph.nodes.length > 0 && (
                <span className="loaded">Ready</span>
              )}
            </div>
          </div>
        </div>

        {/* ── Right Column ── */}
        <div className="platform-dash-side-col">
          {/* Case Intelligence Brief */}
          <Panel
            title="Case Intelligence Brief"
            actions={
              <button className="platform-text-btn" onClick={() => onNavigate("investigations")}>
                Open <ArrowRight size={10} />
              </button>
            }
            empty={!activeCase}
            emptyTitle="Not enough verified information"
            emptyDesc="Not enough verified information to generate a case brief."
          >
            {activeCase && (
              <div className="platform-case-brief">
                <div className="platform-brief-row">
                  <span>Status</span>
                  <span className={`placo-brief-badge ${activeCase.status}`}>{activeCase.status}</span>
                </div>
                {activeCase.scope_statement && (
                  <div className="platform-brief-row">
                    <span>Objective</span>
                    <span className="platform-brief-value" title={activeCase.scope_statement}>
                      {activeCase.scope_statement}
                    </span>
                  </div>
                )}
                <div className="platform-brief-row">
                  <span>Findings</span>
                  <span className="platform-brief-value">{graph.nodes.length} entities, {graph.edges.length} relationships</span>
                </div>
                <div className="platform-brief-row">
                  <span>Last activity</span>
                  <span className="platform-brief-value">{formatTS(activeCase.updated_at)}</span>
                </div>
                {storageStatus && (
                  <div className="platform-brief-row">
                    <span>Local storage</span>
                    <span className="platform-brief-value" title={storageStatus.data_directory}>
                      {storageStatus.writable
                        ? `${(storageStatus.database_bytes / 1024 / 1024).toFixed(1)} MB database`
                        : "Not writable"}
                    </span>
                  </div>
                )}
                {reviewTasks.length > 0 && (
                  <div className="platform-brief-row">
                    <span>Next action</span>
                    <span className="platform-brief-value">{reviewTasks[0].label}</span>
                  </div>
                )}
              </div>
            )}
          </Panel>

          {/* Review Queue */}
          <Panel
            title="Review Queue"
            empty={reviewTasks.length === 0}
            emptyTitle="All clear"
            emptyDesc="No items require review at this time."
          >
            <div className="dashboard-task-list">
              {reviewTasks.map((task) => (
                <button type="button" key={task.label} onClick={() => onNavigate(task.area)}>
                  {task.priority === "high" ? (
                    <AlertTriangle size={11} color="var(--danger)" />
                  ) : task.priority === "medium" ? (
                    <AlertTriangle size={11} color="var(--warning)" />
                  ) : (
                    <CircleDot size={11} />
                  )}
                  <span>{task.label}</span>
                  <ArrowRight size={10} />
                </button>
              ))}
            </div>
          </Panel>

          {/* Local Copilot */}
          <Panel
            title="Local Copilot"
            actions={
              <button className="platform-text-btn" onClick={() => onNavigate("copilot")}>
                Open <ArrowRight size={10} />
              </button>
            }
          >
            <div className="dashboard-copilot">
              <div className="dashboard-copilot-header">
                <Bot size={14} color={modelConfigured ? "var(--accent)" : "var(--text-muted)"} />
                <span>
                  <strong>{modelConfigured ? "Connected" : "Not configured"}</strong>
                  <small>{modelConfigured ? "Model ready" : "Optional — LM Studio or Ollama"}</small>
                </span>
                <span className={`dashboard-copilot-status ${modelConfigured ? "connected" : "disconnected"}`} />
              </div>
              <div className="dashboard-copilot-quick">
                <button type="button" onClick={() => onNavigate("copilot")}>
                  <MessageSquare size={11} /> Summarize case
                </button>
                <button type="button" onClick={() => onNavigate("copilot")}>
                  <Search size={11} /> Find contradictions
                </button>
                <button type="button" onClick={() => onNavigate("copilot")}>
                  <Lightbulb size={11} /> Suggest next steps
                </button>
              </div>
            </div>
          </Panel>
        </div>
      </div>

      {/* ════════════════════════════════════════════ */}
      {/* LEVEL 4: Evidence & Activity (two columns)  */}
      {/* ════════════════════════════════════════════ */}
      <div className="platform-dash-bottom">
        {/* Recent Evidence */}
        <Panel
          title="Recent Evidence"
          actions={
            <button className="platform-text-btn" onClick={() => onNavigate("evidence")}>
              View All <ArrowRight size={10} />
            </button>
          }
          empty={evidenceItems.length === 0}
          emptyTitle="No evidence added"
          emptyDesc="Upload files or add sources to begin building evidence."
        >
          <table className="platform-evidence-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Integrity</th>
                <th>Source</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {evidenceItems.map((s) => (
                <tr key={s.id}>
                  <td style={{ maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis" }}>{s.title}</td>
                  <td>{s.kind}</td>
                <td>
                  <span className="integrity-badge verified">
                    {getEvidenceIntegrity()}
                  </span>
                </td>
                <td className="hash-cell" title={s.id}>{shortHash(s.id)}</td>
                <td>
                  <span className="integrity-badge verified">{getEvidenceStatus(s)}</span>
                </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        {/* Recent Activity */}
        <Panel
          title="Recent Activity"
          empty={recentActivities.length === 0}
          emptyTitle="No recent activity"
          emptyDesc="Timeline events will appear as you work on the case."
        >
          <div className="platform-dash-activity">
            {recentActivities.map((act, i) => (
              <div key={i} className="platform-dash-activity-item">
                <div className="platform-dash-activity-icon">{act.icon}</div>
                <div className="platform-dash-activity-info">
                  <strong>{act.action}</strong>
                  <span>{act.actor}</span>
                </div>
                <span className="platform-dash-activity-time">{act.time}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      {/* ════════════════════════════════════════════ */}
      {/* LEVEL 5: Transform Run History                  */}
      {/* ════════════════════════════════════════════ */}
      <Panel
        title="Transform Run History"
        actions={
          <button className="platform-text-btn" onClick={() => onNavigate("graph")}>
            Run more <ArrowRight size={10} />
          </button>
        }
        loading={transformRunsLoading}
        empty={recentRuns.length === 0}
        emptyTitle="No transforms executed yet"
        emptyDesc="Run an enrichment transform on a graph node and its result will appear here."
      >
        <div className="platform-dash-tools">
          {recentRuns.map((run) => (
            <div key={run.id} className="platform-dash-tool-item">
              <div
                className={`platform-dash-run-icon ${run.status}`}
                aria-hidden="true"
              >
                {run.status === "completed" ? (
                  <Boxes size={13} />
                ) : (
                  <AlertTriangle size={13} />
                )}
              </div>
              <div className="platform-dash-tool-info">
                <strong>{run.transform_title}</strong>
                <span className="platform-dash-run-target">
                  {run.entity_label} · {run.entity_type}
                  {run.status === "completed" && (run.new_nodes > 0 || run.new_edges > 0)
                    ? ` · +${run.new_nodes} nodes · +${run.new_edges} edges`
                    : ""}
                </span>
              </div>
              <div className="platform-dash-tool-meta">
                <span className={`platform-dash-tool-badge ${run.status}`}>
                  {run.status === "completed" ? "Completed" : "Failed"}
                </span>
                <span className="platform-dash-tool-last">{relativeTime(run.created_at)}</span>
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}