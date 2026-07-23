import {
  CheckCircle2,
  Download,
  File,
  FileCheck2,
  Image,
  Link2,
  Search,
  ShieldAlert,
  Trash2,
  Upload,
} from "lucide-react";
import { ChangeEvent, DragEvent, lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import {
  deleteEvidence,
  downloadEvidenceManifest,
  evidencePreviewUrl,
  listEvidence,
  updateEvidence,
  uploadEvidence,
  verifyEvidence,
} from "../../api";
import type { CustodyReport, EvidenceItem, GraphNode, SourceRead, TargetPhoto } from "../../types";
import { EmptyState } from "../../shared/ui/EmptyState";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";

const ForensicsPanel = lazy(() => import("../../ForensicsPanel").then((module) => ({ default: module.ForensicsPanel })));
type EvidenceTab = "files" | "sources" | "custody" | "analyze";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function bytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 ** 2).toFixed(1)} MB`;
}

function canPreview(item: EvidenceItem): boolean {
  return item.mime_type.startsWith("image/") && item.mime_type !== "image/svg+xml";
}

export function EvidenceVaultView({ caseId, sources, photos, custody, entities, onRefresh }: {
  caseId: string;
  sources: SourceRead[];
  photos: TargetPhoto[];
  custody: CustodyReport | null;
  entities: GraphNode[];
  onRefresh: () => Promise<void>;
}) {
  const [tab, setTab] = useState<EvidenceTab>("files");
  const [items, setItems] = useState<EvidenceItem[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [sort, setSort] = useState<"newest" | "name" | "size">("newest");
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [notes, setNotes] = useState("");
  const [tags, setTags] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  async function refreshFiles() {
    const rows = await listEvidence(caseId);
    setItems(rows);
    setSelectedId((current) => rows.some((item) => item.id === current) ? current : (rows[0]?.id ?? ""));
  }

  useEffect(() => {
    let cancelled = false;
    setError("");
    listEvidence(caseId)
      .then((rows) => { if (!cancelled) { setItems(rows); setSelectedId(rows[0]?.id ?? ""); } })
      .catch((cause) => { if (!cancelled) setError(cause instanceof Error ? cause.message : "Could not load managed evidence"); });
    return () => { cancelled = true; abortRef.current?.abort(); };
  }, [caseId]);

  const selected = items.find((item) => item.id === selectedId) ?? null;
  useEffect(() => {
    setNotes(selected?.notes ?? "");
    setTags(selected?.tags.join(", ") ?? "");
  }, [selected]);

  const visible = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return items
      .filter((item) => (!normalized || [item.original_name, item.sha256, item.notes, ...item.tags].some((value) => value.toLowerCase().includes(normalized))) && (typeFilter === "all" || item.mime_type.startsWith(typeFilter)))
      .sort((a, b) => sort === "name" ? a.original_name.localeCompare(b.original_name) : sort === "size" ? b.size_bytes - a.size_bytes : new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, [items, query, sort, typeFilter]);

  async function addFiles(files: File[]) {
    if (files.length === 0) return;
    setUploading(true);
    setError("");
    setMessage("");
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      for (const file of files) {
        if (file.size > 250 * 1024 * 1024) throw new Error(`${file.name} exceeds the 250 MB evidence limit.`);
        await uploadEvidence(caseId, file, "", "", controller.signal);
      }
      await Promise.all([refreshFiles(), onRefresh()]);
      setMessage(`${files.length} file${files.length === 1 ? "" : "s"} hashed, copied, and sealed.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not ingest evidence");
    } finally {
      abortRef.current = null;
      setUploading(false);
    }
  }

  function pickFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    void addFiles(files);
  }

  function drop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    void addFiles(Array.from(event.dataTransfer.files));
  }

  async function saveMetadata() {
    if (!selected) return;
    const updated = await updateEvidence(selected.id, { notes, tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean) });
    setItems((current) => current.map((item) => item.id === updated.id ? updated : item));
    setMessage("Evidence metadata saved.");
  }

  async function toggleEntity(entityId: string) {
    if (!selected) return;
    const entityIds = selected.entity_ids.includes(entityId) ? selected.entity_ids.filter((id) => id !== entityId) : [...selected.entity_ids, entityId];
    const updated = await updateEvidence(selected.id, { entity_ids: entityIds });
    setItems((current) => current.map((item) => item.id === updated.id ? updated : item));
  }

  async function verify(item: EvidenceItem) {
    const result = await verifyEvidence(item.id);
    setMessage(result.intact ? "SHA-256 verification passed." : "Hash mismatch: the managed file no longer matches its ingestion hash.");
    await refreshFiles();
  }

  async function remove(item: EvidenceItem) {
    if (!window.confirm(`Delete the managed copy of “${item.original_name}”? The sealed provenance record remains in the audit trail.`)) return;
    await deleteEvidence(item.id);
    await Promise.all([refreshFiles(), onRefresh()]);
    setMessage("Managed file deleted; provenance was retained.");
  }

  async function exportManifest() {
    const blob = await downloadEvidenceManifest(caseId);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `oihk-basic-evidence-${caseId}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    setMessage("Evidence manifest exported.");
  }

  const tabs: Array<{ id: EvidenceTab; label: string; count?: number }> = [
    { id: "files", label: "Managed files", count: items.length },
    { id: "sources", label: "Sources", count: sources.length },
    { id: "custody", label: "Custody", count: custody?.sealed_count ?? 0 },
    { id: "analyze", label: "Forensic analysis" },
  ];

  return (
    <div className="platform-view evidence-lab">
      <WorkspaceHeader
        eyebrow="Evidence Lab Basic"
        title="Evidence Lab"
        description="Stream files into managed local storage, calculate SHA-256, link entities, and verify integrity later. Files are never executed."
        actions={<><button type="button" onClick={() => void exportManifest()}><Download size={14} /> Manifest</button><span className={custody?.intact ? "platform-health good" : "platform-health warning"}>{custody?.intact ? <CheckCircle2 size={15} /> : <ShieldAlert size={15} />}{custody?.intact ? "Custody verified" : "Review custody"}</span></>}
      />
      {error && <div className="platform-inline-error">{error}</div>}
      {message && <div className="platform-inline-success">{message}</div>}
      <div className="platform-tabs" role="tablist">{tabs.map((item) => <button type="button" role="tab" aria-selected={tab === item.id} className={tab === item.id ? "active" : ""} key={item.id} onClick={() => setTab(item.id)}>{item.label}{item.count !== undefined && <span>{item.count}</span>}</button>)}</div>

      {tab === "files" && <>
        <section className={dragging ? "evidence-dropzone dragging" : "evidence-dropzone"} onDragEnter={(event) => { event.preventDefault(); setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={drop}>
          <input ref={fileRef} type="file" multiple hidden onChange={pickFiles} />
          <Upload size={22} /><div><strong>{uploading ? "Ingesting evidence…" : "Drop evidence files here"}</strong><span>Managed copy · streaming SHA-256 · 250 MB per file</span></div>
          {uploading ? <button type="button" onClick={() => abortRef.current?.abort()}>Cancel</button> : <button type="button" onClick={() => fileRef.current?.click()}>Choose files</button>}
        </section>
        <div className="evidence-layout">
          <section className="platform-section evidence-browser">
            <div className="evidence-toolbar"><label><Search size={13} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name, hash, tag, or note" /></label><select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="all">All types</option><option value="image/">Images</option><option value="text/">Text</option><option value="application/">Documents / binary</option></select><select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}><option value="newest">Newest</option><option value="name">Name</option><option value="size">Largest</option></select></div>
            {visible.length === 0 ? <EmptyState title="No managed evidence" description="Drop a file or use the selector to create a hashed, sealed local copy." /> : <div className="evidence-file-list">{visible.map((item) => <button type="button" key={item.id} className={item.id === selectedId ? "active" : ""} onClick={() => setSelectedId(item.id)}><span className="platform-evidence-icon">{canPreview(item) ? <Image size={16} /> : <File size={16} />}</span><span><strong>{item.original_name}</strong><small>{item.mime_type} · {bytes(item.size_bytes)} · {formatDate(item.created_at)}</small><code>{item.sha256}</code></span>{item.verified_at && <FileCheck2 size={15} />}</button>)}</div>}
          </section>
          <aside className="platform-section evidence-inspector">
            {!selected ? <EmptyState title="Select evidence" description="Choose a managed file to inspect provenance and associations." /> : <>
              <header><div><span className="platform-eyebrow">Evidence record</span><h2>{selected.original_name}</h2></div><button type="button" title="Delete managed file" onClick={() => void remove(selected)}><Trash2 size={13} /></button></header>
              {canPreview(selected) ? <div className="evidence-preview"><img src={evidencePreviewUrl(selected.id)} alt={`Safe preview of ${selected.original_name}`} /></div> : <div className="evidence-no-preview"><File size={24} /><span>Preview disabled for this file type</span><small>OIHK does not render active HTML, SVG, scripts, or unknown binary content.</small></div>}
              <dl className="platform-property-list"><div><dt>SHA-256</dt><dd className="platform-mono">{selected.sha256}</dd></div><div><dt>Size</dt><dd>{bytes(selected.size_bytes)}</dd></div><div><dt>Ingested by</dt><dd>{selected.ingested_by}</dd></div><div><dt>Verified</dt><dd>{selected.verified_at ? formatDate(selected.verified_at) : "Not re-verified"}</dd></div><div><dt>Exports</dt><dd>{selected.export_count}</dd></div></dl>
              <label>Notes<textarea rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} /></label><label>Tags<input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="comma, separated" /></label>
              <div className="evidence-entities"><span>Associated entities</span>{entities.length === 0 ? <small>No graph entities yet.</small> : entities.slice(0, 100).map((entity) => <label key={entity.id}><input type="checkbox" checked={selected.entity_ids.includes(entity.id)} onChange={() => void toggleEntity(entity.id)} /> {entity.label}<small>{entity.type}</small></label>)}</div>
              <div className="evidence-actions"><button type="button" onClick={() => void saveMetadata()}>Save metadata</button><button type="button" onClick={() => void verify(selected)}><FileCheck2 size={13} /> Verify hash</button></div>
            </>}
          </aside>
        </div>
        {photos.length > 0 && <section className="platform-section"><div className="platform-section-heading"><div><span className="platform-eyebrow">Legacy target uploads</span><h2>Target photos</h2></div></div><div className="platform-evidence-list">{photos.map((photo) => <article key={photo.id}><span className="platform-evidence-icon"><Image size={16} /></span><div><strong>{photo.filename}</strong><p className="platform-mono">{photo.sha256}</p><small>{photo.content_type} · {bytes(photo.size_bytes)} · {formatDate(photo.created_at)}</small></div></article>)}</div></section>}
      </>}

      {tab === "sources" && <section className="platform-section"><div className="platform-section-heading"><div><span className="platform-eyebrow">Provenance</span><h2>Collected sources</h2></div></div>{sources.length === 0 ? <EmptyState title="No sources collected" description="OSINT promotions and evidence ingestion create source records here." /> : <div className="platform-evidence-list">{sources.map((source) => <article key={source.id}><span className="platform-evidence-icon"><Link2 size={16} /></span><div><strong>{source.title}</strong><p>{source.citation || source.url || "Internal source"}</p><small>{source.kind} · reliability {Math.round(source.reliability * 100)}% · {formatDate(source.collected_at)}</small></div><span className="platform-status">{source.license}</span></article>)}</div>}</section>}

      {tab === "custody" && <section className="platform-section"><div className="platform-section-heading"><div><span className="platform-eyebrow">Cryptographic verification</span><h2>Chain of custody</h2></div></div>{!custody || custody.entries.length === 0 ? <EmptyState title="No sealed evidence" description="Managed evidence and promoted sources will create custody records." /> : <div className="platform-custody-list">{custody.entries.map((entry) => <div key={entry.sequence}><span className={entry.ok ? "platform-seal good" : "platform-seal bad"}>{entry.ok ? <CheckCircle2 size={14} /> : <ShieldAlert size={14} />}#{entry.sequence}</span><div><strong>{entry.source_title}</strong><small className="platform-mono">{entry.content_sha256}</small></div><time>{formatDate(entry.sealed_at_iso)}</time></div>)}</div>}</section>}

      {tab === "analyze" && <section className="platform-section platform-forensics-host"><div className="platform-section-heading"><div><span className="platform-eyebrow">Read-only forensic pipeline</span><h2>Analyze and seal an upload</h2></div></div><Suspense fallback={<p className="platform-muted">Loading forensic analyzer…</p>}><ForensicsPanel caseId={caseId} onAnalyzed={() => void Promise.all([refreshFiles(), onRefresh()])} /></Suspense></section>}
    </div>
  );
}
