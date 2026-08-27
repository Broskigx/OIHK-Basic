import { AlertTriangle, Ban, Link2, LoaderCircle, Power, RefreshCw, ShieldCheck, Unplug } from "lucide-react";
import type { LinkedSystemModule, SystemLinkModuleState } from "../types";
import { moduleActionsForState, type ModulePowerAction } from "./modulePowerModel";

const STATE_LABELS: Record<SystemLinkModuleState, string> = {
  NOT_INSTALLED: "NOT INSTALLED",
  UNLINKED: "UNLINKED",
  PAIRING: "PAIRING",
  LINKED_OFF: "OFF",
  STARTING: "STARTING",
  AUTHENTICATING: "AUTHENTICATING",
  READY: "READY",
  BUSY: "BUSY",
  STOPPING: "STOPPING",
  ERROR: "ERROR",
  INCOMPATIBLE: "INCOMPATIBLE",
  REVOKED: "REVOKED",
  DISABLED: "DISABLED",
  QUARANTINED: "QUARANTINED",
};

function ActionIcon({ action }: { action: ModulePowerAction }) {
  if (action === "restart") return <RefreshCw size={14} />;
  if (action === "pair") return <Link2 size={14} />;
  if (action === "revoke") return <Unplug size={14} />;
  if (action === "disable") return <Ban size={14} />;
  if (action === "open") return <ShieldCheck size={14} />;
  if (action === "cancel") return <AlertTriangle size={14} />;
  return <Power size={14} />;
}

const ACTION_LABELS: Record<ModulePowerAction, string> = {
  start: "Power On",
  stop: "Power Off",
  restart: "Restart",
  cancel: "Cancel",
  disable: "Disable",
  enable: "Enable",
  revoke: "Revoke link",
  pair: "Create Link Key",
  open: "Open module",
};

/** Initials for a module with no brand of its own: "OIHK Triage Suite" -> "TS". */
function ModuleBrand({ module }: { module: LinkedSystemModule }) {
  const initials = module.product_name
    .split(/\s+/)
    .filter((word) => word && word.toUpperCase() !== "OIHK")
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");
  return (
    <div className="evidence-lab-brand" aria-label={module.product_name}>
      <span>OIHK</span>
      <strong>{initials || "M"}</strong>
    </div>
  );
}

export function ModulePowerCard({
  module,
  brand,
  busy,
  onAction,
}: {
  module: LinkedSystemModule;
  // Optional: a module that ships no brand of its own gets initials rather
  // than the host having to know about it by name.
  brand?: React.ReactNode;
  busy: boolean;
  onAction: (action: ModulePowerAction) => void;
}) {
  const actions = moduleActionsForState(module.state);
  const active = module.state === "READY" || module.state === "BUSY";
  const transitional = ["STARTING", "AUTHENTICATING", "STOPPING"].includes(module.state);
  return (
    <article className={`system-link-power-card state-${module.state.toLowerCase()}`}>
      <header>
        {brand ?? <ModuleBrand module={module} />}
        <div>
          <span className="platform-eyebrow">First-party OIHK product</span>
          <h2>{module.product_name}</h2>
          <small>{module.module_version ? `v${module.module_version} · System Link ${module.protocol_version}` : "Separate local installation"}</small>
        </div>
        <span className={`system-link-state ${active ? "active" : ""}`}>
          {transitional && <LoaderCircle className="spin" size={13} />}
          <i />{STATE_LABELS[module.state]}
        </span>
      </header>
      <div className="system-link-card-body">
        <p>
          {active
            ? "Runtime authenticated, healthy, and local-only. Signed module categories are active."
            : module.state === "LINKED_OFF"
              ? "Secure pairing is preserved while the Evidence Lab runtime is off."
              : module.last_error_detail || "Evidence Lab remains optional; OIHK Basic continues independently."}
        </p>
        {module.module_fingerprint && <code title={module.module_fingerprint}>Identity {module.module_fingerprint.slice(0, 16)}…</code>}
        {module.granted_capabilities.length > 0 && (
          <div className="system-link-capabilities">
            {module.granted_capabilities.map((capability) => <span key={capability}>{capability}</span>)}
          </div>
        )}
      </div>
      <footer>
        {actions.map((action) => (
          <button
            type="button"
            key={action}
            className={action === "start" || action === "open" ? "platform-primary" : ""}
            disabled={busy}
            onClick={() => onAction(action)}
          >
            <ActionIcon action={action} />{ACTION_LABELS[action]}
          </button>
        ))}
      </footer>
    </article>
  );
}
