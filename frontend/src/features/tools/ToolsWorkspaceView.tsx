import {
  Binary,
  CheckCircle2,
  Database,
  FileArchive,
  FileSearch,
  Fingerprint,
  FlaskConical,
  History,
  Image,
  LockKeyhole,
  Microscope,
  ScanSearch,
  ShieldAlert,
} from "lucide-react";
import { lazy, Suspense, useMemo, useState } from "react";
import type { CustodyReport, SourceRead } from "../../types";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import { ForensicAnalysisWorkspace } from "./ForensicAnalysisWorkspace";
import { forensicArtifactSources, forensicSourceLabel } from "./forensicModel";

const ForensicLab = lazy(() =>
  import("../../ForensicLab").then((module) => ({ default: module.ForensicLab })),
);
const ForensicsPanel = lazy(() =>
  import("../../ForensicsPanel").then((module) => ({ default: module.ForensicsPanel })),
);

type ForensicTab = "analyze" | "media" | "artifacts" | "lab";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function ArtifactHistory({ sources, custody, onOpenEvidence }: { sources: SourceRead[]; custody: CustodyReport | null; onOpenEvidence: () => void }) {
  const artifacts = useMemo(() => forensicArtifactSources(sources), [sources]);
  const [selectedId, setSelectedId] = useState("");
  const selected = artifacts.find((item) => item.id === selectedId) ?? artifacts[0];
  const seal = custody?.entries.find((entry) => entry.source_id === selected?.id);

  if (artifacts.length === 0) {
    return (
      <div className="forensic-empty-result forensic-artifact-empty">
        <FileArchive size={24} />
        <strong>No forensic artifacts in this investigation</strong>
        <p>Run a full analysis, media inspection, IOC scan, or carving operation to create sealed evidence.</p>
      </div>
    );
  }

  return (
    <div className="forensic-artifact-layout">
      <div className="forensic-artifact-list" aria-label="Persisted forensic artifacts">
        {artifacts.map((artifact) => {
          const artifactSeal = custody?.entries.find((entry) => entry.source_id === artifact.id);
          return (
            <button
              type="button"
              key={artifact.id}
              className={selected?.id === artifact.id ? "active" : ""}
              onClick={() => setSelectedId(artifact.id)}
            >
              <span className="forensic-artifact-icon">
                {artifact.kind === "forensic_media" ? <Image size={16} /> : artifact.kind === "carved_artifact" ? <FileArchive size={16} /> : <FileSearch size={16} />}
              </span>
              <div>
                <strong>{artifact.title}</strong>
                <small>{forensicSourceLabel(artifact.kind)} · {formatDate(artifact.collected_at)}</small>
              </div>
              <span className={artifactSeal?.ok ? "forensic-artifact-seal good" : "forensic-artifact-seal"}>
                <LockKeyhole size={12} />{artifactSeal?.ok ? `#${artifactSeal.sequence}` : "No seal loaded"}
              </span>
            </button>
          );
        })}
      </div>

      {selected && (
        <aside className="forensic-artifact-inspector">
          <span className="platform-eyebrow">Persisted evidence record</span>
          <h3>{selected.title}</h3>
          <p>{forensicSourceLabel(selected.kind)}</p>
          <dl>
            <div><dt>Source ID</dt><dd className="platform-mono">{selected.id}</dd></div>
            <div><dt>Citation</dt><dd className="platform-mono">{selected.citation || "Internal evidence reference"}</dd></div>
            <div><dt>Reliability</dt><dd>{Math.round(selected.reliability * 100)}%</dd></div>
            <div><dt>Collected</dt><dd>{formatDate(selected.collected_at)}</dd></div>
            <div><dt>Custody</dt><dd>{seal ? (seal.ok ? `Verified · sequence #${seal.sequence}` : `Review sequence #${seal.sequence}`) : "Seal not present in loaded custody report"}</dd></div>
            {seal && <div><dt>Content SHA-256</dt><dd className="platform-mono">{seal.content_sha256}</dd></div>}
          </dl>
          <div className={seal?.ok ? "forensic-integrity-note good" : "forensic-integrity-note"}>
            {seal?.ok ? <CheckCircle2 size={15} /> : <ShieldAlert size={15} />}
            <span>{seal?.ok ? "Stored content and custody chain verify correctly." : "Open Evidence to inspect the complete custody chain."}</span>
          </div>
          <button type="button" onClick={onOpenEvidence}>Open Evidence</button>
          <small>The artifact inventory exposes provenance and seal state. Raw evidence remains in protected backend storage.</small>
        </aside>
      )}
    </div>
  );
}

export function ToolsWorkspaceView({
  caseId,
  isAdmin,
  sources,
  custody,
  onRefresh,
  onOpenEvidence,
}: {
  caseId: string;
  isAdmin: boolean;
  sources: SourceRead[];
  custody: CustodyReport | null;
  onRefresh: () => Promise<void>;
  onOpenEvidence: () => void;
}) {
  const [tab, setTab] = useState<ForensicTab>("analyze");
  const artifactCount = useMemo(() => forensicArtifactSources(sources).length, [sources]);
  const tabs: Array<{ id: ForensicTab; label: string; count?: number; icon: typeof Microscope }> = [
    { id: "analyze", label: "Full analysis", icon: Microscope },
    { id: "media", label: "Media / stego", icon: ScanSearch },
    { id: "artifacts", label: "Artifact history", count: artifactCount, icon: History },
    { id: "lab", label: "Intelligence lab", icon: FlaskConical },
  ];

  return (
    <div className="platform-view forensic-workspace-view">
      <WorkspaceHeader
        eyebrow="Investigation workspace"
        title="Forensics"
        description="Local artifact analysis, forensic intelligence, and cryptographic custody. Operations run on the configured OIHK backend without external enrichment."
        actions={
          <div className="forensic-header-states">
            <span><Database size={14} />Local execution</span>
            <span className={custody?.intact ? "good" : "warning"}>
              {custody?.intact ? <CheckCircle2 size={14} /> : <ShieldAlert size={14} />}
              {custody ? (custody.intact ? "Custody intact" : "Custody review") : "Custody unavailable"}
            </span>
          </div>
        }
      />

      <div className="forensic-capability-strip" aria-label="Local forensic pipeline capabilities">
        <div><Fingerprint size={16} /><span>Identity</span><strong>SHA-256 · SHA-1 · MD5</strong></div>
        <div><Binary size={16} /><span>Structure</span><strong>MIME · magic · entropy</strong></div>
        <div><FileSearch size={16} /><span>Extraction</span><strong>Metadata · text · IOC</strong></div>
        <div><LockKeyhole size={16} /><span>Integrity</span><strong>Persisted · sealed · auditable</strong></div>
      </div>

      <div className="platform-tabs forensic-workspace-tabs" role="tablist" aria-label="Forensic workspaces">
        {tabs.map(({ id, label, count, icon: Icon }) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
            <Icon size={14} />{label}{count !== undefined && <span>{count}</span>}
          </button>
        ))}
      </div>

      {tab === "analyze" && (
        <section className="platform-section forensic-primary-section">
          <div className="platform-section-heading">
            <div><span className="platform-eyebrow">Deterministic local pipeline</span><h2>Analyze, persist, and seal one artifact</h2></div>
          </div>
          <p className="platform-footnote">Supported extraction depends on the file format. A successful run always returns backend-authored results and a persisted custody reference.</p>
          <ForensicAnalysisWorkspace caseId={caseId} onCompleted={onRefresh} />
        </section>
      )}

      {tab === "media" && (
        <section className="platform-section platform-forensics-host forensic-media-section">
          <div className="platform-section-heading">
            <div><span className="platform-eyebrow">Media-specific inspection</span><h2>Steganography and appended-data signals</h2></div>
          </div>
          <p className="platform-footnote">Runs OIHK's media heuristics, stores the uploaded bytes, creates a provenance source, and seals the original content.</p>
          <Suspense fallback={<p className="platform-muted">Loading media analyzer…</p>}>
            <ForensicsPanel caseId={caseId} onAnalyzed={() => void onRefresh()} />
          </Suspense>
        </section>
      )}

      {tab === "artifacts" && (
        <section className="platform-section forensic-history-section">
          <div className="platform-section-heading">
            <div><span className="platform-eyebrow">Case-scoped inventory</span><h2>Persisted forensic artifacts</h2></div>
          </div>
          <ArtifactHistory sources={sources} custody={custody} onOpenEvidence={onOpenEvidence} />
        </section>
      )}

      {tab === "lab" && (
        <section className="platform-section platform-forensics-host forensic-lab-section">
          <div className="platform-section-heading">
            <div><span className="platform-eyebrow">Local forensic intelligence</span><h2>Hash sets, case correlation, carving, and rules</h2></div>
          </div>
          <p className="platform-footnote">Correlation uses OIHK's organization-scoped local index. Hash sets and rules are administered locally; carving seals every recovered child artifact.</p>
          <Suspense fallback={<p className="platform-muted">Loading forensic intelligence lab…</p>}>
            <ForensicLab caseId={caseId} isAdmin={isAdmin} />
          </Suspense>
        </section>
      )}
    </div>
  );
}
