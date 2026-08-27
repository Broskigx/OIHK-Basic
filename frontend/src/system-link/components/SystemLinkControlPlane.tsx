import { CheckCircle2, Copy, Link2, RefreshCw, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import type { PlatformArea } from "../../app/navigation";
import type { useSystemLinkRegistry } from "../registry";
import { ModulePowerCard } from "./ModulePowerCard";
import type { ModulePowerAction } from "./modulePowerModel";

type Registry = ReturnType<typeof useSystemLinkRegistry>;

function PendingApproval({ pending, onApprove }: { pending: Registry["pending"][number]; onApprove: (values: string[]) => void }) {
  const [selected, setSelected] = useState(pending.requested_capabilities);
  useEffect(() => setSelected(pending.requested_capabilities), [pending]);
  return (
    <section className="platform-section system-link-approval">
      <div className="platform-section-heading"><div><span className="platform-eyebrow">Approval required</span><h2>{pending.product_name}</h2></div><ShieldCheck size={18} /></div>
      <p>Identity <code>{pending.module_fingerprint.slice(0, 20)}…</code> proved possession of its private key and its package hash is valid. Grant only the capabilities you accept.</p>
      <div className="system-link-grant-list">
        {pending.requested_capabilities.map((capability) => (
          <label key={capability}><input type="checkbox" checked={selected.includes(capability)} onChange={() => setSelected((current) => current.includes(capability) ? current.filter((value) => value !== capability) : [...current, capability])} /><code>{capability}</code></label>
        ))}
      </div>
      <button type="button" className="platform-primary" onClick={() => onApprove(selected)}><CheckCircle2 size={14} /> Approve bounded grant</button>
    </section>
  );
}

export function SystemLinkControlPlane({ registry, onNavigate }: { registry: Registry; onNavigate: (area: PlatformArea) => void }) {
  // Every module the host knows about, linked or merely advertised. This used
  // to `find` one hard-coded module id, which meant any other module paired
  // successfully and was then invisible in the only screen that can start,
  // stop or revoke it.
  const modules = registry.status?.modules ?? [];

  function action(moduleId: string, value: ModulePowerAction) {
    if (value === "pair") {
      void registry.beginPairing();
      return;
    }
    if (value === "open") {
      const target = modules.find((module) => module.module_id === moduleId);
      const route = target?.categories.find((category) => category.enabled)?.route_id;
      if (route) onNavigate(route as PlatformArea);
      return;
    }
    if (value === "revoke" && !window.confirm("Revoke this System Link? Evidence and case data will be preserved, but new pairing will be required.")) return;
    void registry.runAction(moduleId, value);
  }

  return (
    <div className="platform-view system-link-view">
      <WorkspaceHeader
        eyebrow="Local application control plane"
        title="OIHK System Link"
        description="Pair, permission, start, stop, and monitor separately installed first-party OIHK products. Runtime state never changes link trust implicitly."
        actions={<button type="button" onClick={() => void registry.refresh()} disabled={registry.loading}><RefreshCw size={14} /> Refresh</button>}
      />
      {registry.error && <div className="platform-inline-error">{registry.error}</div>}
      {registry.status && (
        <section className="system-link-identity-strip">
          <ShieldCheck size={18} />
          <div><strong>Basic installation identity</strong><code>{registry.status.installation_fingerprint}</code></div>
          <span>Protocol {registry.status.protocol_version} · {registry.status.key_storage}</span>
        </section>
      )}
      {registry.pairing && (
        <section className="platform-section system-link-key-panel">
          <div><span className="platform-eyebrow">Single-use bootstrap credential</span><h2>OIHK Link Key</h2></div>
          <code>{registry.pairing.link_key}</code>
          <button type="button" onClick={() => void navigator.clipboard.writeText(registry.pairing!.link_key)}><Copy size={14} /> Copy</button>
          <p><Link2 size={14} /> Expires {new Date(registry.pairing.expires_at).toLocaleTimeString()}. It is consumed by pairing and never becomes a permanent bearer token.</p>
        </section>
      )}
      {registry.pending.map((pending) => <PendingApproval key={pending.pairing_id} pending={pending} onApprove={(grants) => void registry.approvePairing(pending.pairing_id, grants)} />)}
      <div className="system-link-module-grid">
        {modules.map((module) => (
          <ModulePowerCard
            key={module.module_id}
            module={module}
            busy={registry.busyModule === module.module_id}
            onAction={(value) => action(module.module_id, value)}
          />
        ))}
      </div>
      <p className="platform-footnote">No module receives raw SQLite, arbitrary filesystem, private Tauri state, shell execution, or capabilities outside its explicit grant.</p>
    </div>
  );
}
