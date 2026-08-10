import {
  Activity,
  Bot,
  CheckCircle2,
  Copy,
  Database,
  Download,
  Gauge,
  Info,
  LockKeyhole,
  Link2,
  Palette,
  PlayCircle,
  RefreshCw,
  Save,
  Server,
  Settings2,
  ShieldAlert,
  SlidersHorizontal,
  Wrench,
} from "lucide-react";
import { useEffect, useState } from "react";
import { downloadStorageBackup } from "../../api";
import type { ApplicationSettings, DesktopStatus, ProviderCatalog, StorageStatus, User } from "../../types";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import { PRODUCT_VERSION, UPDATE_CHANNEL } from "../../version";
import { UpdatePanel } from "../updates/UpdatePanel";
import type { UpdateController } from "../updates/useUpdater";

type SettingsSection = "general" | "appearance" | "storage" | "models" | "system-link" | "tools" | "privacy" | "performance" | "transfer" | "diagnostics" | "about";

const SECTIONS: Array<{ id: SettingsSection; label: string; icon: typeof Settings2 }> = [
  { id: "general", label: "General", icon: Settings2 },
  { id: "appearance", label: "Appearance", icon: Palette },
  { id: "storage", label: "Storage", icon: Database },
  { id: "models", label: "Local Models", icon: Bot },
  { id: "system-link", label: "OIHK System Link", icon: Link2 },
  { id: "tools", label: "Tools", icon: Wrench },
  { id: "privacy", label: "Privacy", icon: LockKeyhole },
  { id: "performance", label: "Performance", icon: Gauge },
  { id: "transfer", label: "Import / Export", icon: Download },
  { id: "diagnostics", label: "Diagnostics", icon: Activity },
  { id: "about", label: "About", icon: Info },
];

function bytes(value?: number): string {
  if (value === undefined) return "Unavailable";
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

export function SettingsView({
  user,
  desktopStatus,
  providers,
  settings,
  storage,
  loading,
  error,
  onRefresh,
  onSave,
  onRunOnboarding,
  onOpenModels,
  onOpenSystemLink,
  updater,
}: {
  user: User;
  desktopStatus: DesktopStatus | null;
  providers: ProviderCatalog | null;
  settings: ApplicationSettings | null;
  storage: StorageStatus | null;
  loading: boolean;
  error: string;
  onRefresh: () => void;
  onSave: (settings: ApplicationSettings) => Promise<void>;
  onRunOnboarding: () => void;
  onOpenModels: () => void;
  onOpenSystemLink: () => void;
  updater: UpdateController;
}) {
  const [section, setSection] = useState<SettingsSection>("general");
  const [draft, setDraft] = useState<ApplicationSettings | null>(settings);
  const [message, setMessage] = useState("");

  useEffect(() => setDraft(settings), [settings]);

  async function save() {
    if (!draft) return;
    setMessage("");
    await onSave(draft);
    setMessage("Settings saved locally.");
  }

  async function backup() {
    try {
      const blob = await downloadStorageBackup();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `oihk-basic-${new Date().toISOString().slice(0, 10)}.sqlite3`;
      anchor.click();
      URL.revokeObjectURL(url);
      setMessage("Consistent SQLite backup created.");
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Could not create backup");
    }
  }

  async function copyDiagnostics() {
    const diagnostic = {
      product: desktopStatus?.product ?? "OIHK Basic",
      version: desktopStatus?.version ?? `${PRODUCT_VERSION} development`,
      platform: desktopStatus?.platform ?? navigator.platform,
      runtime: desktopStatus?.mode ?? "browser",
      backend: desktopStatus?.api_endpoint ?? "configured local API",
      storage_writable: storage?.writable ?? null,
      storage_bytes: storage?.total_bytes ?? null,
      providers: providers ? { operational: providers.operational, configured: providers.configured } : null,
      user_role: user.role,
    };
    await navigator.clipboard.writeText(JSON.stringify(diagnostic, null, 2));
    setMessage("Sanitized diagnostics copied. No paths, case data, or credentials were included.");
  }

  if (!draft) {
    return <div className="platform-view"><WorkspaceHeader title="Settings" description="Loading local preferences…" /><div className="platform-inline-error">{error || "Local settings are unavailable."}</div></div>;
  }

  return (
    <div className="platform-view settings-view">
      <WorkspaceHeader
        eyebrow="Local configuration"
        title="Settings"
        description="Versioned preferences, storage controls, privacy defaults, and sanitized runtime diagnostics."
        actions={<><button type="button" onClick={onRefresh} disabled={loading}><RefreshCw size={14} /> Refresh</button><button type="button" className="platform-primary" onClick={() => void save()} disabled={loading}><Save size={14} /> Save</button></>}
      />
      {error && <div className="platform-inline-error">{error}</div>}
      {message && <div className="platform-inline-success">{message}</div>}

      <div className="settings-layout">
        <nav className="settings-nav" aria-label="Settings sections">
          {SECTIONS.map((item) => <button type="button" key={item.id} className={section === item.id ? "active" : ""} onClick={() => setSection(item.id)}><item.icon size={14} /> {item.label}</button>)}
        </nav>

        <section className="platform-section settings-panel">
          {section === "general" && <>
            <div className="platform-section-heading"><div><span className="platform-eyebrow">General</span><h2>Workspace behavior</h2></div></div>
            <div className="settings-form-grid">
              <label>Language<select value={draft.general.language} onChange={(event) => setDraft({ ...draft, general: { ...draft.general, language: event.target.value as "en" | "es" } })}><option value="en">English</option><option value="es">Español</option></select></label>
              <label>Default start<select value={draft.general.default_start} onChange={(event) => setDraft({ ...draft, general: { ...draft.general, default_start: event.target.value } })}><option value="dashboard">Dashboard</option><option value="investigations">Investigations</option><option value="graph">Intelligence Graph</option></select></label>
              <label>Default investigation<input value={draft.general.default_case_id} onChange={(event) => setDraft({ ...draft, general: { ...draft.general, default_case_id: event.target.value } })} placeholder="Use most recent" /></label>
              <label className="settings-check"><input type="checkbox" checked={draft.general.confirmations} onChange={(event) => setDraft({ ...draft, general: { ...draft.general, confirmations: event.target.checked } })} /> Confirm destructive actions</label>
              <label className="settings-check"><input type="checkbox" checked={draft.general.check_updates} onChange={(event) => setDraft({ ...draft, general: { ...draft.general, check_updates: event.target.checked } })} /> Check for updates</label>
              <label>Update channel<select value={draft.general.update_channel} onChange={(event) => setDraft({ ...draft, general: { ...draft.general, update_channel: event.target.value as "alpha" | "beta" | "stable" } })}><option value="alpha">Alpha</option><option value="beta">Beta (reserved)</option><option value="stable">Stable (reserved)</option></select></label>
            </div>
            <div className="settings-actions"><button type="button" onClick={onRunOnboarding}><PlayCircle size={14} /> Run onboarding again</button></div>
            <UpdatePanel updater={updater} recovery={desktopStatus?.recovery} />
          </>}

          {section === "appearance" && <>
            <div className="platform-section-heading"><div><span className="platform-eyebrow">Appearance</span><h2>Readable, low-distraction layout</h2></div></div>
            <div className="settings-form-grid">
              <label>Density<select value={draft.appearance.density} onChange={(event) => setDraft({ ...draft, appearance: { ...draft.appearance, density: event.target.value as "comfortable" | "compact" } })}><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></label>
              <label>Text scale<input type="range" min="0.85" max="1.3" step="0.05" value={draft.appearance.text_scale} onChange={(event) => setDraft({ ...draft, appearance: { ...draft.appearance, text_scale: Number(event.target.value) } })} /><span>{Math.round(draft.appearance.text_scale * 100)}%</span></label>
              <label className="settings-check"><input type="checkbox" checked={draft.appearance.dark_mode} readOnly /> Dark mode (Basic theme)</label>
              <label className="settings-check"><input type="checkbox" checked={draft.appearance.reduce_motion} onChange={(event) => setDraft({ ...draft, appearance: { ...draft.appearance, reduce_motion: event.target.checked } })} /> Reduce motion</label>
              <label className="settings-check"><input type="checkbox" checked={draft.appearance.restore_layout} onChange={(event) => setDraft({ ...draft, appearance: { ...draft.appearance, restore_layout: event.target.checked } })} /> Restore workspace layout</label>
            </div>
          </>}

          {section === "storage" && <>
            <div className="platform-section-heading"><div><span className="platform-eyebrow">Storage</span><h2>Local data custody</h2></div><span className={`platform-status ${storage?.writable ? "success" : ""}`}>{storage?.writable ? "Writable" : "Unavailable"}</span></div>
            <dl className="platform-property-list settings-properties">
              <div><dt>Application data</dt><dd className="platform-mono">{storage?.data_directory ?? "Loading…"}</dd></div>
              <div><dt>Database</dt><dd>{bytes(storage?.database_bytes)}</dd></div>
              <div><dt>Evidence files</dt><dd>{bytes(storage?.evidence_bytes)}</dd></div>
              <div><dt>Total measured</dt><dd>{bytes(storage?.total_bytes)}</dd></div>
            </dl>
            <div className="settings-form-grid"><label className="settings-check"><input type="checkbox" checked={draft.storage.backup_on_exit} onChange={(event) => setDraft({ ...draft, storage: { ...draft.storage, backup_on_exit: event.target.checked } })} /> Request backup on exit</label><label>Retention days<input type="number" min="0" max="36500" value={draft.storage.retention_days} onChange={(event) => setDraft({ ...draft, storage: { ...draft.storage, retention_days: Number(event.target.value) } })} /><small>0 keeps records indefinitely.</small></label></div>
            <div className="settings-actions"><button type="button" onClick={() => void backup()}><Download size={14} /> Download SQLite backup</button></div>
            <p className="platform-footnote">The recommended platform directory is selected on first run. Moving a live database is intentionally unavailable because it could corrupt open case data.</p>
          </>}

          {section === "models" && <>
            <div className="platform-section-heading"><div><span className="platform-eyebrow">Local Models</span><h2>LM Studio, Ollama, and private endpoints</h2></div><Bot size={18} /></div>
            <div className="settings-callout"><p>Model endpoints, task routing, context limits, and inference tests are managed in the dedicated Local Models workspace.</p><button type="button" onClick={onOpenModels}>Open Local Models</button></div>
          </>}

          {section === "system-link" && <>
            <div className="platform-section-heading"><div><span className="platform-eyebrow">OIHK System Link</span><h2>Linked local products</h2></div><Link2 size={18} /></div>
            <div className="settings-callout"><p>Pair separately installed first-party OIHK products, review bounded capability grants, and control verified runtimes without exposing shell or raw database access.</p><button type="button" onClick={onOpenSystemLink}>Open System Link control plane</button></div>
          </>}

          {section === "tools" && <>
            <div className="platform-section-heading"><div><span className="platform-eyebrow">Tools</span><h2>Local execution boundaries</h2></div></div>
            <div className="settings-form-grid"><label>Tool timeout (seconds)<input type="number" min="1" max="3600" value={draft.tools.timeout_seconds} onChange={(event) => setDraft({ ...draft, tools: { ...draft.tools, timeout_seconds: Number(event.target.value) } })} /></label><label>Maximum file size (MB)<input type="number" min="1" max="4096" value={draft.tools.max_file_mb} onChange={(event) => setDraft({ ...draft, tools: { ...draft.tools, max_file_mb: Number(event.target.value) } })} /></label></div>
            <p className="platform-footnote">Executable paths are never guessed from a developer machine. Packaged tools use application-relative resources or explicit environment configuration.</p>
          </>}

          {section === "privacy" && <>
            <div className="platform-section-heading"><div><span className="platform-eyebrow">Privacy</span><h2>Outbound connections and logs</h2></div><LockKeyhole size={18} /></div>
            <div className="settings-form-grid">
              <label className="settings-check"><input type="checkbox" checked={draft.privacy.telemetry_enabled} onChange={(event) => setDraft({ ...draft, privacy: { ...draft.privacy, telemetry_enabled: event.target.checked } })} /> Anonymous telemetry (off by default)</label>
              <label className="settings-check"><input type="checkbox" checked={draft.privacy.public_osint_enabled} onChange={(event) => setDraft({ ...draft, privacy: { ...draft.privacy, public_osint_enabled: event.target.checked } })} /> Allow explicit public OSINT lookups</label>
              <label className="settings-check"><input type="checkbox" checked={draft.privacy.redact_logs} onChange={(event) => setDraft({ ...draft, privacy: { ...draft.privacy, redact_logs: event.target.checked } })} /> Redact sensitive log fields</label>
              <label>Log retention (days)<input type="number" min="1" max="365" value={draft.privacy.log_retention_days} onChange={(event) => setDraft({ ...draft, privacy: { ...draft.privacy, log_retention_days: Number(event.target.value) } })} /></label>
            </div>
            <div className="settings-network-list"><strong>Possible connections</strong><span>Local API on 127.0.0.1</span><span>Signed update metadata only when update checks are enabled</span><span>User-selected LM Studio or Ollama endpoint</span><span>Public DNS, RDAP, and certificate services only after an OSINT action</span></div>
          </>}

          {section === "performance" && <>
            <div className="platform-section-heading"><div><span className="platform-eyebrow">Performance</span><h2>Renderer and resource limits</h2></div><SlidersHorizontal size={18} /></div>
            <div className="settings-form-grid"><label>Graph quality<select value={draft.performance.quality} onChange={(event) => setDraft({ ...draft, performance: { ...draft.performance, quality: event.target.value as ApplicationSettings["performance"]["quality"] } })}><option value="balanced">Balanced</option><option value="quality">Quality</option><option value="performance">Performance</option></select></label><label>Maximum visible nodes<input type="number" min="100" max="100000" value={draft.performance.max_visible_nodes} onChange={(event) => setDraft({ ...draft, performance: { ...draft.performance, max_visible_nodes: Number(event.target.value) } })} /></label><label className="settings-check"><input type="checkbox" checked={draft.performance.worker_enabled} onChange={(event) => setDraft({ ...draft, performance: { ...draft.performance, worker_enabled: event.target.checked } })} /> Use background workers</label><label className="settings-check"><input type="checkbox" checked={draft.performance.low_power_mode} onChange={(event) => setDraft({ ...draft, performance: { ...draft.performance, low_power_mode: event.target.checked } })} /> Low-power mode</label></div>
          </>}

          {section === "transfer" && <>
            <div className="platform-section-heading"><div><span className="platform-eyebrow">Import / Export</span><h2>Portable local data</h2></div></div>
            <div className="settings-callout"><p>Investigation JSON imports and exports are available from Investigations. A consistent SQLite backup captures all structured local data.</p><button type="button" onClick={() => void backup()}><Download size={14} /> Export structured database</button></div>
            <p className="platform-footnote">Restoring a database while it is open is blocked. Close OIHK Basic and use the documented recovery procedure to avoid partial writes.</p>
          </>}

          {section === "diagnostics" && <>
            <div className="platform-section-heading"><div><span className="platform-eyebrow">Diagnostics</span><h2>Sanitized runtime status</h2></div><Activity size={18} /></div>
            <dl className="platform-property-list settings-properties"><div><dt>Runtime</dt><dd>{desktopStatus?.mode ?? "browser"}</dd></div><div><dt>Version</dt><dd>{desktopStatus?.version ?? `${PRODUCT_VERSION} development`}</dd></div><div><dt>Platform</dt><dd>{desktopStatus?.platform ?? navigator.platform}</dd></div><div><dt>Backend</dt><dd>{desktopStatus?.backend_managed ? "Managed local process" : "Local web service"}</dd></div><div><dt>Providers</dt><dd>{providers ? `${providers.operational} operational / ${providers.configured} configured` : "Unavailable"}</dd></div><div><dt>Storage</dt><dd>{storage?.writable ? "Writable" : "Check local service"}</dd></div></dl>
            <div className="settings-actions"><button type="button" onClick={() => void copyDiagnostics()}><Copy size={14} /> Copy sanitized diagnostics</button></div>
          </>}

          {section === "about" && <>
            <div className="platform-section-heading"><div><span className="platform-eyebrow">About</span><h2>OIHK Basic</h2></div><Server size={18} /></div>
            <dl className="platform-property-list settings-properties"><div><dt>Edition</dt><dd>Basic · local-first · single-user</dd></div><div><dt>Version</dt><dd>{desktopStatus?.version ?? PRODUCT_VERSION} · {UPDATE_CHANNEL}</dd></div><div><dt>Account</dt><dd>{user.username} ({user.role})</dd></div><div><dt>Settings schema</dt><dd>v{draft.schema_version}</dd></div></dl>
            {providers && <div className="platform-table-wrap"><table className="platform-table"><thead><tr><th>Provider</th><th>Access</th><th>Status</th></tr></thead><tbody>{providers.providers.map((provider) => <tr key={provider.id}><td><strong>{provider.name}</strong><small>{provider.capabilities.join(", ")}</small></td><td>{provider.access}</td><td><span className={provider.status === "operational" ? "platform-provider good" : "platform-provider"}>{provider.status === "operational" ? <CheckCircle2 size={13} /> : <ShieldAlert size={13} />}{provider.status}</span></td></tr>)}</tbody></table></div>}
          </>}
        </section>
      </div>
    </div>
  );
}
