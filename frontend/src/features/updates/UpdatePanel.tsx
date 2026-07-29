import { CheckCircle2, Download, FolderOpen, RefreshCw, RotateCw, ShieldCheck, X } from "lucide-react";
import type { DesktopRecoveryStatus } from "../../types";
import { PRODUCT_VERSION, UPDATE_CHANNEL } from "../../version";
import type { UpdateController } from "./useUpdater";

function size(value: number): string {
  if (!value) return "Size supplied when download starts";
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

export function UpdatePanel({
  updater,
  recovery,
}: {
  updater: UpdateController;
  recovery?: DesktopRecoveryStatus | null;
}) {
  const { state } = updater;
  const percent = state.totalBytes ? Math.min(100, Math.round((state.downloadedBytes / state.totalBytes) * 100)) : 0;

  return (
    <section className="platform-section update-panel" aria-live="polite">
      <div className="platform-section-heading">
        <div><span className="platform-eyebrow">Signed updates</span><h2>Application updates</h2></div>
        <span className={`platform-status ${state.phase === "current" ? "success" : ""}`}>{state.phase.replace(/_/g, " ")}</span>
      </div>

      {!updater.supported && <p>Update checks are available in the installed desktop application.</p>}
      {state.phase === "idle" && updater.supported && <p>No automatic installation is performed. OIHK only checks availability at startup.</p>}
      <p className="platform-footnote">Installed: OIHK Basic {PRODUCT_VERSION} · {UPDATE_CHANNEL}</p>
      {state.phase === "checking" && <p><RefreshCw size={14} className="spin" /> Checking the signed alpha channel…</p>}
      {state.phase === "current" && <p><CheckCircle2 size={14} /> This installation is current.</p>}
      {state.targetVersion && (
        <dl className="platform-property-list">
          <div><dt>Version</dt><dd>{state.currentVersion} → {state.targetVersion}</dd></div>
          <div><dt>Published</dt><dd>{state.publishedAt || "Not supplied"}</dd></div>
          <div><dt>Download</dt><dd>{size(state.totalBytes)}</dd></div>
        </dl>
      )}
      {state.notes && <div className="update-notes"><strong>Release notes</strong><p>{state.notes}</p></div>}
      {state.phase === "downloading" && (
        <div className="update-progress">
          <progress max={state.totalBytes || 1} value={state.downloadedBytes} />
          <span>{state.totalBytes ? `${percent}%` : `${size(state.downloadedBytes)} downloaded`}</span>
        </div>
      )}
      {state.phase === "verifying" && <p><ShieldCheck size={14} /> Verifying the mandatory updater signature…</p>}
      {state.phase === "preparing_backup" && <p><ShieldCheck size={14} /> Draining writes and verifying the pre-update SQLite backup…</p>}
      {state.phase === "ready_to_restart" && <p>The signed package and verified backup are ready. Restart only when no analysis is running.</p>}
      {state.phase === "installing" && <p><RotateCw size={14} className="spin" /> Stopping the local service and installing…</p>}
      {state.message && <div className={state.phase === "error" ? "platform-inline-error" : "platform-inline-success"}>{state.message}</div>}

      {recovery && ["error", "migration_failed", "migration_backup_failed", "installing"].includes(recovery.stage) && (
        <div className="platform-inline-error">
          Update recovery is required ({recovery.error_code || recovery.stage}). Preserve the current database, verify the backup SHA-256 and SQLite integrity, then continue the current version or reinstall a signed version. See the update recovery guide before replacing data.
        </div>
      )}

      <div className="settings-actions">
        {updater.supported && ["idle", "current", "deferred", "error"].includes(state.phase) && (
          <button type="button" onClick={() => void updater.checkForUpdates()}><RefreshCw size={14} /> Check again</button>
        )}
        {state.phase === "available" && (
          <>
            <button type="button" className="platform-primary" onClick={() => void updater.download()}><Download size={14} /> Download and install</button>
            <button type="button" onClick={() => void updater.defer()}><X size={14} /> Not now</button>
          </>
        )}
        {["downloading", "verifying", "preparing_backup"].includes(state.phase) && (
          <button type="button" onClick={() => void updater.defer()}><X size={14} /> Cancel safely</button>
        )}
        {state.phase === "ready_to_restart" && (
          <>
            <button type="button" className="platform-primary" onClick={() => void updater.install()}><RotateCw size={14} /> Restart and update</button>
            <button type="button" onClick={() => void updater.defer()}>Continue current version</button>
          </>
        )}
        {(state.backupPath || recovery?.backup_path) && (
          <button type="button" onClick={() => void updater.openBackupFolder()}><FolderOpen size={14} /> Open backup folder</button>
        )}
        {recovery && ["error", "migration_failed", "migration_backup_failed", "installing"].includes(recovery.stage) && (
          <button type="button" onClick={() => void updater.defer()}>Dismiss and continue current version</button>
        )}
      </div>
      <p className="platform-footnote">Cancelling a transfer is best-effort; installation is never started after cancellation. Signatures are mandatory and invalid packages are blocked.</p>
    </section>
  );
}
