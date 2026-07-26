import { Database, HardDrive, LockKeyhole, Server, ShieldCheck } from "lucide-react";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import type { DesktopStatus } from "../../types";
import { PRODUCT_VERSION, UPDATE_CHANNEL } from "../../version";
import { UpdatePanel } from "../updates/UpdatePanel";
import type { UpdateController } from "../updates/useUpdater";

export function AboutView({
  desktopStatus,
  updater,
}: {
  desktopStatus: DesktopStatus | null;
  updater: UpdateController;
}) {
  return (
    <div className="platform-view about-view">
      <WorkspaceHeader
        eyebrow="OIHK Basic"
        title="Local investigation workspace"
        description="A focused, single-user edition for evidence-aware research, link analysis, and local model assistance."
      />
      <div className="about-hero platform-section">
        <div className="about-mark">OIHK<span>Basic</span></div>
        <div>
          <h2>Private by architecture</h2>
          <p>Your case database, evidence metadata, graph, reports, and Copilot history are stored by the local OIHK service. No cloud AI provider is required.</p>
        </div>
        <span className="platform-status success"><ShieldCheck size={14} /> Local-first</span>
      </div>
      <div className="about-grid">
        <section className="platform-section"><Database size={20} /><h2>SQLite persistence</h2><p>Investigations, graph data, source provenance, OSINT history, and local Copilot conversations survive restarts.</p></section>
        <section className="platform-section"><LockKeyhole size={20} /><h2>Explicit actions</h2><p>OSINT findings remain drafts until promoted. The Copilot proposes analysis but never changes case data automatically.</p></section>
        <section className="platform-section"><Server size={20} /><h2>Local models</h2><p>Connect LM Studio, Ollama, or a private OpenAI-compatible server under your control.</p></section>
        <section className="platform-section"><HardDrive size={20} /><h2>Desktop-ready</h2><p>The Tauri shell manages the local backend and keeps the Basic edition isolated from OIHK Full.</p></section>
      </div>
      <section className="platform-section">
        <div className="platform-section-heading"><div><span className="platform-eyebrow">Runtime</span><h2>Build information</h2></div></div>
        <dl className="platform-property-list">
          <div><dt>Product</dt><dd>{desktopStatus?.product ?? "OIHK Basic"}</dd></div>
          <div><dt>Version</dt><dd>{desktopStatus?.version ?? PRODUCT_VERSION} · {UPDATE_CHANNEL}</dd></div>
          <div><dt>Runtime</dt><dd>{desktopStatus ? `${desktopStatus.mode} · ${desktopStatus.platform}` : "Browser development mode"}</dd></div>
          <div><dt>Local API</dt><dd className="platform-mono">{desktopStatus?.api_endpoint ?? "http://127.0.0.1:8000"}</dd></div>
        </dl>
      </section>
      <UpdatePanel updater={updater} recovery={desktopStatus?.recovery} />
    </div>
  );
}
