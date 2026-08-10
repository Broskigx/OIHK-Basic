import {
  AlertTriangle,
  Binary,
  CheckCircle2,
  Clock3,
  Copy,
  Download,
  FileCode2,
  FileSearch,
  Fingerprint,
  Hash,
  ListTree,
  LoaderCircle,
  LockKeyhole,
  Microscope,
  SearchCode,
  ShieldCheck,
  Upload,
  X,
} from "lucide-react";
import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { analyzeForensicCore } from "../../api";
import type { ForensicCoreReport } from "../../types";
import { forensicReportCounts, formatByteSize, groupForensicIocs } from "./forensicModel";

const MAX_UPLOAD_BYTES = 64 * 1024 * 1024;
const TEXT_PREVIEW_LIMIT = 30_000;
type ResultTab = "overview" | "metadata" | "indicators" | "content" | "timeline";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "medium" }).format(new Date(value));
}

function saveAnalysis(report: ForensicCoreReport) {
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${report.filename.replace(/[^a-z0-9._-]+/gi, "_")}.forensic.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function CopyHashButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="forensic-copy-button"
      onClick={() => {
        if (!navigator.clipboard) return;
        void navigator.clipboard.writeText(value).then(() => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1500);
        }).catch(() => setCopied(false));
      }}
      aria-label="Copy hash"
      title={copied ? "Copied" : "Copy hash"}
    >
      {copied ? <CheckCircle2 size={13} /> : <Copy size={13} />}
    </button>
  );
}

function AnalysisOverview({ report }: { report: ForensicCoreReport }) {
  const analysis = report.file_analysis;
  return (
    <div className="forensic-result-grid">
      <section className="forensic-panel forensic-file-facts">
        <header>
          <FileSearch size={16} />
          <div>
            <span>File identity</span>
            <strong>{analysis?.detected_label || "Unknown file type"}</strong>
          </div>
        </header>
        <dl>
          <div><dt>MIME</dt><dd>{analysis?.mime_type || "Unavailable"}</dd></div>
          <div><dt>Detected type</dt><dd>{analysis?.detected_type || "Unknown"}</dd></div>
          <div><dt>Extension</dt><dd>{analysis?.extension || "None"}</dd></div>
          <div><dt>Size</dt><dd>{formatByteSize(analysis?.size_bytes ?? 0)}</dd></div>
          <div><dt>Entropy</dt><dd>{analysis?.entropy ?? "Unavailable"}</dd></div>
          <div><dt>Magic bytes</dt><dd className="platform-mono">{analysis?.magic_bytes || "Unavailable"}</dd></div>
        </dl>
      </section>

      <section className="forensic-panel forensic-custody-card">
        <header>
          <LockKeyhole size={16} />
          <div>
            <span>Evidence persistence</span>
            <strong>{report.custody_sealed ? "Stored and custody-sealed" : "Not sealed"}</strong>
          </div>
        </header>
        <dl>
          <div><dt>Source ID</dt><dd className="platform-mono">{report.source_id || "Unavailable"}</dd></div>
          <div><dt>Custody sequence</dt><dd>{report.custody_sequence ? `#${report.custody_sequence}` : "Unavailable"}</dd></div>
          <div><dt>Stored SHA-256</dt><dd className="platform-mono">{report.stored_sha256 || "Unavailable"}</dd></div>
        </dl>
      </section>

      <section className="forensic-panel forensic-hash-panel">
        <header>
          <Hash size={16} />
          <div>
            <span>Cryptographic identity</span>
            <strong>{report.hashes.length} digests computed</strong>
          </div>
        </header>
        <div className="forensic-hash-list">
          {report.hashes.map((hash) => (
            <div key={hash.algorithm}>
              <span>{hash.algorithm}</span>
              <code>{hash.digest}</code>
              <CopyHashButton value={hash.digest} />
            </div>
          ))}
        </div>
      </section>

      <section className="forensic-panel forensic-discrepancy-panel">
        <header>
          <AlertTriangle size={16} />
          <div>
            <span>Consistency checks</span>
            <strong>{analysis?.discrepancies.length ? `${analysis.discrepancies.length} finding(s)` : "No discrepancies"}</strong>
          </div>
        </header>
        {analysis?.discrepancies.length ? (
          <ul>{analysis.discrepancies.map((item) => <li key={item}>{item}</li>)}</ul>
        ) : (
          <p>No MIME, extension, or magic-byte inconsistencies were reported.</p>
        )}
      </section>
    </div>
  );
}

function MetadataResult({ report }: { report: ForensicCoreReport }) {
  const metadata = report.metadata;
  if (!metadata || metadata.fields.length === 0) {
    return <div className="forensic-empty-result"><Binary size={22} /><strong>No metadata fields extracted</strong><p>The selected format may not expose a supported metadata container.</p></div>;
  }
  return (
    <div className="forensic-metadata-table">
      {metadata.fields.slice(0, 250).map((field, index) => (
        <div key={`${field.category}-${field.key}-${index}`}>
          <span>{field.category}</span>
          <strong>{field.key}</strong>
          <code>{field.value}</code>
        </div>
      ))}
      {metadata.fields.length > 250 && <p className="platform-footnote">Showing the first 250 fields. Export JSON for the complete result.</p>}
      {metadata.errors.map((error) => <p className="forensic-inline-error" key={error}>{error}</p>)}
    </div>
  );
}

function IndicatorResult({ report }: { report: ForensicCoreReport }) {
  const matches = report.iocs?.matches ?? [];
  const groups = groupForensicIocs(matches);
  if (matches.length === 0) {
    return <div className="forensic-empty-result"><SearchCode size={22} /><strong>No indicators extracted</strong><p>No supported IP, URL, domain, email, hash, CVE, ASN, or related selector was found.</p></div>;
  }
  return (
    <div className="forensic-ioc-groups">
      {groups.map((group) => (
        <section key={group.type}>
          <header><span>{group.type}</span><strong>{group.matches.length}</strong></header>
          {group.matches.slice(0, 100).map((match, index) => (
            <div className="forensic-ioc-row" key={`${match.value}-${index}`}>
              <code>{match.display || match.value}</code>
              <span>{Math.round(match.confidence * 100)}%</span>
              <p>{match.context || "No surrounding context stored."}</p>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}

function ContentResult({ report }: { report: ForensicCoreReport }) {
  const extraction = report.text_extraction;
  if (!extraction || !extraction.text) {
    return <div className="forensic-empty-result"><FileCode2 size={22} /><strong>No text extracted</strong><p>This file did not contain text supported by the local extraction pipeline.</p></div>;
  }
  const truncated = extraction.text.length > TEXT_PREVIEW_LIMIT;
  return (
    <div className="forensic-content-result">
      <div><span>{extraction.format}</span><strong>{extraction.word_count.toLocaleString()} words</strong><small>{extraction.char_count.toLocaleString()} characters</small></div>
      <pre>{extraction.text.slice(0, TEXT_PREVIEW_LIMIT)}</pre>
      {truncated && <p className="platform-footnote">Preview limited to {TEXT_PREVIEW_LIMIT.toLocaleString()} characters. Export JSON for the complete extraction.</p>}
      {extraction.errors.map((error) => <p className="forensic-inline-error" key={error}>{error}</p>)}
    </div>
  );
}

function TimelineResult({ report }: { report: ForensicCoreReport }) {
  if (report.timeline_events.length === 0) {
    return <div className="forensic-empty-result"><Clock3 size={22} /><strong>No forensic timestamps found</strong><p>The pipeline did not derive a reliable timestamp from this artifact.</p></div>;
  }
  return (
    <div className="forensic-event-list">
      {report.timeline_events.map((event) => (
        <article key={event.event_id}>
          <i aria-hidden="true" />
          <time>{formatDate(event.timestamp)}</time>
          <div><span>{event.event_type}</span><strong>{event.title}</strong><p>{event.detail}</p></div>
        </article>
      ))}
    </div>
  );
}

export function ForensicAnalysisWorkspace({ caseId, onCompleted }: { caseId: string; onCompleted: () => Promise<void> }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ForensicCoreReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [resultTab, setResultTab] = useState<ResultTab>("overview");

  const counts = report ? forensicReportCounts(report) : null;

  function acceptFile(nextFile: File | undefined) {
    setError("");
    setReport(null);
    if (!nextFile) {
      setFile(null);
      return;
    }
    if (nextFile.size > MAX_UPLOAD_BYTES) {
      setFile(null);
      setError("The file exceeds the 64 MB limit enforced by the forensic service.");
      return;
    }
    if (nextFile.size === 0) {
      setFile(null);
      setError("Empty files cannot be analyzed.");
      return;
    }
    setFile(nextFile);
  }

  function onInput(event: ChangeEvent<HTMLInputElement>) {
    acceptFile(event.target.files?.[0]);
    event.target.value = "";
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    acceptFile(event.dataTransfer.files?.[0]);
  }

  async function analyze() {
    if (!file || busy) return;
    setBusy(true);
    setError("");
    setReport(null);
    setResultTab("overview");
    try {
      const result = await analyzeForensicCore(caseId, file);
      setReport(result);
      try {
        await onCompleted();
      } catch {
        setError("Analysis completed and was sealed, but the investigation inventory could not be refreshed.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The local forensic analysis failed.");
    } finally {
      setBusy(false);
    }
  }

  const tabs: Array<{ id: ResultTab; label: string; count?: number }> = [
    { id: "overview", label: "Overview", count: counts?.hashes },
    { id: "metadata", label: "Metadata", count: counts?.metadata },
    { id: "indicators", label: "Indicators", count: counts?.indicators },
    { id: "content", label: "Extracted text", count: report?.text_extraction?.word_count ?? 0 },
    { id: "timeline", label: "File timeline", count: counts?.timeline },
  ];

  return (
    <div className="forensic-analysis-workspace">
      {!report && (
        <div className="forensic-intake-grid">
          <section className="forensic-intake-card">
            <header><span>01</span><div><strong>Select evidence</strong><p>The file stays inside the OIHK backend configured for this workspace.</p></div></header>
            <div
              className={dragging ? "forensic-dropzone dragging" : "forensic-dropzone"}
              onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
            >
              <input ref={inputRef} type="file" hidden onChange={onInput} />
              <span className="forensic-drop-icon"><Upload size={22} /></span>
              {file ? (
                <div className="forensic-selected-file">
                  <strong>{file.name}</strong>
                  <span>{file.type || "Unknown MIME"} · {formatByteSize(file.size)}</span>
                  <button type="button" onClick={() => acceptFile(undefined)} aria-label="Remove selected file"><X size={14} /></button>
                </div>
              ) : (
                <div><strong>Drop one artifact here</strong><span>or choose a local file · maximum 64 MB</span></div>
              )}
              {!file && <button type="button" onClick={() => inputRef.current?.click()}>Choose file</button>}
            </div>
          </section>

          <section className="forensic-intake-card forensic-pipeline-card">
            <header><span>02</span><div><strong>Run local pipeline</strong><p>One operation computes, extracts, persists, and seals the result.</p></div></header>
            <ol>
              <li><Fingerprint size={15} /><div><strong>Cryptographic hashing</strong><span>SHA-256, SHA-1, and MD5</span></div></li>
              <li><Binary size={15} /><div><strong>File inspection</strong><span>MIME, magic bytes, entropy, discrepancies</span></div></li>
              <li><FileCode2 size={15} /><div><strong>Content extraction</strong><span>Metadata, text, indicators, timestamps</span></div></li>
              <li><ShieldCheck size={15} /><div><strong>Evidence custody</strong><span>Persistent source and cryptographic seal</span></div></li>
            </ol>
            <button type="button" className="platform-primary forensic-run-button" disabled={!file || busy} onClick={() => void analyze()}>
              {busy ? <LoaderCircle className="forensic-spin" size={16} /> : <Microscope size={16} />}
              {busy ? "Analyzing and sealing…" : "Analyze and seal"}
            </button>
          </section>
        </div>
      )}

      {error && <div className="forensic-workspace-error" role="alert"><AlertTriangle size={15} /><span>{error}</span></div>}

      {report && (
        <section className="forensic-result-shell">
          <header className="forensic-result-header">
            <div className="forensic-result-file"><span><CheckCircle2 size={18} /></span><div><small>Analysis completed</small><h2>{report.filename}</h2><p>{report.file_analysis?.detected_label || "Unknown type"} · {formatByteSize(report.file_analysis?.size_bytes ?? 0)}</p></div></div>
            <div className="forensic-result-actions">
              <span className={report.custody_sealed ? "forensic-sealed-state" : "forensic-unsealed-state"}><LockKeyhole size={14} />{report.custody_sealed ? `Sealed #${report.custody_sequence}` : "Not sealed"}</span>
              <button type="button" onClick={() => saveAnalysis(report)}><Download size={14} />Export JSON</button>
              <button type="button" onClick={() => { setReport(null); setFile(null); }}><Upload size={14} />New analysis</button>
            </div>
          </header>

          <div className="forensic-result-tabs" role="tablist" aria-label="Forensic analysis result">
            {tabs.map((tab) => (
              <button key={tab.id} type="button" role="tab" aria-selected={resultTab === tab.id} className={resultTab === tab.id ? "active" : ""} onClick={() => setResultTab(tab.id)}>
                {tab.id === "overview" && <ListTree size={14} />}
                {tab.id === "metadata" && <Binary size={14} />}
                {tab.id === "indicators" && <SearchCode size={14} />}
                {tab.id === "content" && <FileCode2 size={14} />}
                {tab.id === "timeline" && <Clock3 size={14} />}
                {tab.label}<span>{tab.count ?? 0}</span>
              </button>
            ))}
          </div>

          <div className="forensic-result-body">
            {resultTab === "overview" && <AnalysisOverview report={report} />}
            {resultTab === "metadata" && <MetadataResult report={report} />}
            {resultTab === "indicators" && <IndicatorResult report={report} />}
            {resultTab === "content" && <ContentResult report={report} />}
            {resultTab === "timeline" && <TimelineResult report={report} />}
          </div>

          {report.errors.length > 0 && (
            <footer className="forensic-result-errors">
              <AlertTriangle size={15} />
              <div><strong>Pipeline notices</strong>{report.errors.map((item) => <p key={item}>{item}</p>)}</div>
            </footer>
          )}
        </section>
      )}
    </div>
  );
}
