import {
  Activity,
  ArrowRight,
  Bot,
  CheckCircle2,
  CircleAlert,
  ClipboardList,
  Cpu,
  Database,
  FileArchive,
  FolderKanban,
  HardDrive,
  Link2,
  Loader2,
  Plus,
  RefreshCw,
  ServerOff,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getDashboardSummary } from "../../api";
import type { PlatformArea } from "../../app/navigation";
import type { DashboardSummary, LocalModelRuntimeStatus, StorageStatus } from "../../types";
import { formatByteSize } from "../../utils";
import { buildDashboardMetrics, dashboardActionLabel, type DashboardMetric } from "./dashboardModel";

const METRIC_ICONS = {
  investigations: FolderKanban,
  evidence: FileArchive,
  tasks: ClipboardList,
  modules: Link2,
} as const;

function formatDate(value: string | null): string {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not available";
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function relativeTime(value: string): string {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "Unknown time";
  const seconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
  if (seconds < 60) return "Just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function providerLabel(provider: string): string {
  if (provider === "lmstudio") return "LM Studio";
  if (provider === "ollama") return "Ollama";
  if (provider === "openai_compatible") return "OpenAI-compatible";
  return "Local model";
}

function StatusBadge({ state }: { state: string }) {
  const normalized = state.toLowerCase().replace(/_/g, "-");
  return <span className={`status-badge status-${normalized}`}>{state.replace(/_/g, " ")}</span>;
}

function Panel({
  title,
  icon: Icon,
  action,
  children,
  className = "",
}: {
  title: string;
  icon?: typeof Activity;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`dashboard-panel ${className}`.trim()}>
      <header className="dashboard-panel-header">
        <div>{Icon && <Icon size={15} aria-hidden="true" />}<h2>{title}</h2></div>
        {action}
      </header>
      <div className="dashboard-panel-body">{children}</div>
    </section>
  );
}

function MetricCard({ metric }: { metric: DashboardMetric }) {
  const Icon = METRIC_ICONS[metric.key];
  return (
    <article className={`dashboard-metric metric-${metric.tone}`}>
      <span className="dashboard-metric-icon"><Icon size={20} aria-hidden="true" /></span>
      <div>
        <span>{metric.label}</span>
        <strong>{metric.value}</strong>
        <small>{metric.detail}</small>
      </div>
    </article>
  );
}

function DashboardSkeleton() {
  return (
    <div className="dashboard-loading" role="status" aria-label="Loading dashboard">
      <div className="dashboard-metrics">
        {Array.from({ length: 4 }, (_, index) => <span key={index} className="dashboard-skeleton metric" />)}
      </div>
      <div className="dashboard-primary-grid">
        <span className="dashboard-skeleton panel" />
        <span className="dashboard-skeleton panel" />
      </div>
    </div>
  );
}

export function DashboardContent({
  summary,
  loading,
  error,
  storageStatus,
  localModelStatus,
  localModelLoading,
  onRetry,
  onRefreshLocalModel,
  onNavigate,
  onOpenCase,
  onNewCase,
}: {
  summary: DashboardSummary | null;
  loading: boolean;
  error: string;
  storageStatus: StorageStatus | null;
  localModelStatus: LocalModelRuntimeStatus | null;
  localModelLoading: boolean;
  onRetry: () => void;
  onRefreshLocalModel: () => void;
  onNavigate: (area: PlatformArea) => void;
  onOpenCase: (caseId: string) => void;
  onNewCase: () => void;
}) {
  const metrics = useMemo(() => (summary ? buildDashboardMetrics(summary) : []), [summary]);

  return (
    <div className="platform-dashboard">
      <header className="dashboard-heading">
        <div>
          <h1>Dashboard</h1>
          <p>Local investigation overview.</p>
        </div>
        <div className="dashboard-heading-actions">
          <button type="button" className="platform-ghost-btn" onClick={onRetry} disabled={loading}>
            <RefreshCw size={14} className={loading ? "spin" : ""} /> Refresh
          </button>
          <button type="button" className="platform-primary-btn" onClick={onNewCase}>
            <Plus size={15} /> New investigation
          </button>
        </div>
      </header>

      {error && !summary && (
        <div className="dashboard-error" role="alert">
          <CircleAlert size={20} />
          <div><strong>Dashboard data is unavailable</strong><span>{error}</span></div>
          <button type="button" onClick={onRetry}>Try again</button>
        </div>
      )}

      {loading && !summary ? <DashboardSkeleton /> : summary && (
        <>
          {error && <div className="dashboard-stale-note" role="status">Showing the latest available data. Refresh failed: {error}</div>}
          <div className="dashboard-metrics" aria-label="Dashboard metrics">
            {metrics.map((metric) => <MetricCard key={metric.key} metric={metric} />)}
          </div>

          <div className="dashboard-primary-grid">
            <Panel
              title="Recent investigations"
              icon={FolderKanban}
              action={<button type="button" className="dashboard-panel-link" onClick={() => onNavigate("investigations")}>View all <ArrowRight size={13} /></button>}
            >
              {summary.recent_investigations.length === 0 ? (
                <div className="dashboard-empty">
                  <FolderKanban size={24} />
                  <strong>No investigations yet</strong>
                  <span>Create a local investigation to begin collecting evidence and relationships.</span>
                  <button type="button" onClick={onNewCase}><Plus size={14} /> Create investigation</button>
                </div>
              ) : (
                <div className="dashboard-table-wrap">
                  <table className="dashboard-table">
                    <thead><tr><th>Investigation</th><th>Status</th><th>Evidence</th><th>Updated</th></tr></thead>
                    <tbody>
                      {summary.recent_investigations.map((investigation) => (
                        <tr key={investigation.id}>
                          <td><button type="button" onClick={() => onOpenCase(investigation.id)}>{investigation.title}</button><small>{investigation.priority} priority</small></td>
                          <td><StatusBadge state={investigation.status} /></td>
                          <td>{investigation.evidence_count}</td>
                          <td><time dateTime={investigation.updated_at ?? undefined}>{formatDate(investigation.updated_at)}</time></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Panel>

            <Panel title="Recent activity" icon={Activity}>
              {summary.recent_activity.length === 0 ? (
                <div className="dashboard-empty compact">
                  <Activity size={22} />
                  <strong>No recorded activity</strong>
                  <span>Audited investigation and System Link events will appear here.</span>
                </div>
              ) : (
                <ol className="dashboard-activity-list">
                  {summary.recent_activity.slice(0, 8).map((item) => (
                    <li key={item.id}>
                      <span className={`activity-marker ${item.kind}`} />
                      <div><strong>{dashboardActionLabel(item.action)}</strong><span>{item.detail} · {item.actor}</span></div>
                      <time dateTime={item.created_at} title={formatDate(item.created_at)}>{relativeTime(item.created_at)}</time>
                    </li>
                  ))}
                </ol>
              )}
            </Panel>
          </div>

          <div className="dashboard-status-grid">
            <Panel title="Local state" icon={HardDrive}>
              {storageStatus ? (
                <dl className="dashboard-status-list">
                  <div><dt><Database size={15} />SQLite database</dt><dd><strong>{formatByteSize(storageStatus.database_bytes)}</strong><span>{storageStatus.writable ? "Writable" : "Read-only"}</span></dd></div>
                  <div><dt><FileArchive size={15} />Managed evidence</dt><dd><strong>{formatByteSize(storageStatus.evidence_bytes)}</strong><span>Local storage</span></dd></div>
                  <div><dt><HardDrive size={15} />OIHK data</dt><dd><strong>{formatByteSize(storageStatus.total_bytes)}</strong><span>Database + evidence</span></dd></div>
                </dl>
              ) : <div className="dashboard-empty compact"><ServerOff size={22} /><strong>Storage status unavailable</strong><span>Retry from Settings.</span></div>}
            </Panel>

            <Panel
              title="Local model"
              icon={Cpu}
              action={<button type="button" className="dashboard-icon-button" onClick={onRefreshLocalModel} disabled={localModelLoading} aria-label="Test local model connection" title="Test connection"><RefreshCw size={14} className={localModelLoading ? "spin" : ""} /></button>}
            >
              {localModelStatus ? (
                <div className="dashboard-model-state">
                  <div><span className={`connection-dot ${localModelStatus.connected ? "connected" : "offline"}`} /><div><strong>{providerLabel(localModelStatus.provider)}</strong><span>{localModelStatus.connected ? "Connected" : localModelStatus.error === "StatusUnavailable" ? "Status unavailable" : localModelStatus.configured ? "Offline" : "Not configured"}</span></div></div>
                  <dl>
                    <div><dt>Model</dt><dd>{localModelStatus.model || "No active model"}</dd></div>
                    <div><dt>Endpoint</dt><dd title={localModelStatus.endpoint}>{localModelStatus.endpoint || "Not configured"}</dd></div>
                    {localModelStatus.connected && <div><dt>Available</dt><dd>{localModelStatus.model_count} model{localModelStatus.model_count === 1 ? "" : "s"}</dd></div>}
                    {localModelStatus.context_length !== null && <div><dt>Context</dt><dd>{localModelStatus.context_length.toLocaleString("en-US")} tokens</dd></div>}
                    {localModelStatus.max_tokens !== null && <div><dt>Output limit</dt><dd>{localModelStatus.max_tokens.toLocaleString("en-US")} tokens</dd></div>}
                  </dl>
                  {!localModelStatus.model_available && localModelStatus.model && localModelStatus.connected && <p className="dashboard-warning">The selected model is not advertised by the endpoint.</p>}
                  <button type="button" className="dashboard-secondary-action" onClick={() => onNavigate("models")}>Open model settings <ArrowRight size={13} /></button>
                </div>
              ) : <div className="dashboard-empty compact"><Loader2 className="spin" size={22} /><strong>Checking local model</strong></div>}
            </Panel>

            <Panel title="System Link" icon={Link2} action={<button type="button" className="dashboard-panel-link" onClick={() => onNavigate("system-link")}>Manage <ArrowRight size={13} /></button>}>
              {summary.modules.length === 0 ? (
                <div className="dashboard-empty compact"><Link2 size={22} /><strong>No linked modules</strong><span>External products remain separated until paired and trusted.</span></div>
              ) : (
                <ul className="dashboard-module-list">
                  {summary.modules.map((module) => (
                    <li key={module.module_id}>
                      <span className={`connection-dot ${["READY", "BUSY"].includes(module.state) ? "connected" : module.state === "ERROR" || module.state === "QUARANTINED" ? "error" : "offline"}`} />
                      <div><strong>{module.product_name}</strong><span>v{module.module_version}{module.last_activity_at ? ` · ${relativeTime(module.last_activity_at)}` : ""}</span></div>
                      <StatusBadge state={module.state} />
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          <div className="dashboard-capability-note">
            <CheckCircle2 size={14} />
            <span>All counts come from authorized local records. {summary.counts.tasks_available ? "Task metrics are backed by the local task registry." : "Task metrics remain unavailable until OIHK exposes a task registry."}</span>
            <button type="button" onClick={() => onNavigate("copilot")}><Bot size={13} /> Open Copilot</button>
          </div>
        </>
      )}
    </div>
  );
}

export function DashboardView({
  refreshKey,
  storageStatus,
  localModelStatus,
  localModelLoading,
  onRefreshLocalModel,
  onNavigate,
  onOpenCase,
  onNewCase,
}: {
  refreshKey: string;
  storageStatus: StorageStatus | null;
  localModelStatus: LocalModelRuntimeStatus | null;
  localModelLoading: boolean;
  onRefreshLocalModel: () => void;
  onNavigate: (area: PlatformArea) => void;
  onOpenCase: (caseId: string) => void;
  onNewCase: () => void;
}) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadVersion, setReloadVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    getDashboardSummary()
      .then((result) => { if (!cancelled) setSummary(result); })
      .catch((cause) => { if (!cancelled) setError(cause instanceof Error ? cause.message : "Could not load dashboard data"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [refreshKey, reloadVersion]);

  return (
    <DashboardContent
      summary={summary}
      loading={loading}
      error={error}
      storageStatus={storageStatus}
      localModelStatus={localModelStatus}
      localModelLoading={localModelLoading}
      onRetry={() => setReloadVersion((value) => value + 1)}
      onRefreshLocalModel={onRefreshLocalModel}
      onNavigate={onNavigate}
      onOpenCase={onOpenCase}
      onNewCase={onNewCase}
    />
  );
}
