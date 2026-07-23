import {
  AlertTriangle,
  CheckCircle2,
  Database,
  GitBranch,
  History,
  Search,
  ShieldCheck,
  Square,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { getOsintHistory, osintLookup, promoteOsintQuery } from "../../api";
import { EmptyState } from "../../shared/ui/EmptyState";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import type { OsintLookupResult, OsintQuery } from "../../types";

type LookupType = "auto" | "domain" | "ip" | "email" | "url" | "username" | "phone" | "hash" | "text" | "crypto";

const LOOKUP_TYPES: Array<{ id: LookupType; label: string; available: boolean }> = [
  { id: "auto", label: "Auto-detect", available: true },
  { id: "domain", label: "Domain", available: true },
  { id: "ip", label: "IP address", available: true },
  { id: "email", label: "Email", available: true },
  { id: "url", label: "URL (domain lookup)", available: true },
  { id: "username", label: "Username", available: false },
  { id: "phone", label: "Phone", available: false },
  { id: "hash", label: "File hash", available: false },
  { id: "text", label: "Free text", available: false },
  { id: "crypto", label: "Crypto address", available: false },
];

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function resultFromHistory(row: OsintQuery): OsintLookupResult {
  return {
    query_id: row.id,
    value: row.value,
    kind: row.kind,
    summary: `Stored ${row.kind} lookup for ${row.value}`,
    findings: row.findings,
    errors: row.errors,
    entities: [],
    relationships: [],
    source: null,
    promoted: row.promoted,
  };
}

function normalizeValue(type: LookupType, raw: string): string {
  const value = raw.trim();
  if (type !== "url") return value;
  const candidate = /^https?:\/\//i.test(value) ? value : `https://${value}`;
  try {
    return new URL(candidate).hostname;
  } catch {
    throw new Error("Enter a valid URL, for example https://example.org/path.");
  }
}

export function OsintWorkspaceView({ caseId, onGraphChanged, onOpenGraph }: {
  caseId: string;
  onGraphChanged: () => Promise<void>;
  onOpenGraph: () => void;
}) {
  const [type, setType] = useState<LookupType>("auto");
  const [value, setValue] = useState("");
  const [history, setHistory] = useState<OsintQuery[]>([]);
  const [result, setResult] = useState<OsintLookupResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [promoting, setPromoting] = useState(false);
  const [error, setError] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  async function refreshHistory() {
    setHistory(await getOsintHistory(caseId));
  }

  useEffect(() => {
    let cancelled = false;
    setResult(null);
    setError("");
    getOsintHistory(caseId)
      .then((rows) => { if (!cancelled) setHistory(rows); })
      .catch((cause) => { if (!cancelled) setError(cause instanceof Error ? cause.message : "Could not load lookup history"); });
    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, [caseId]);

  const selectedAdapter = useMemo(() => LOOKUP_TYPES.find((item) => item.id === type)!, [type]);

  async function runLookup(event: FormEvent) {
    event.preventDefault();
    setError("");
    setResult(null);
    if (!selectedAdapter.available) {
      setError(`${selectedAdapter.label} has no built-in local adapter. Add a lawful data source before running this query type.`);
      return;
    }
    if (value.trim().length < 2) {
      setError("Enter at least two characters.");
      return;
    }
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    try {
      const lookup = await osintLookup({ case_id: caseId, value: normalizeValue(type, value) }, controller.signal);
      setResult(lookup);
      await refreshHistory();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Lookup failed");
    } finally {
      abortRef.current = null;
      setLoading(false);
    }
  }

  async function promote() {
    if (!result?.query_id || result.promoted) return;
    setPromoting(true);
    setError("");
    try {
      const promoted = await promoteOsintQuery(result.query_id);
      setResult(promoted);
      await Promise.all([refreshHistory(), onGraphChanged()]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not add the result to the graph");
    } finally {
      setPromoting(false);
    }
  }

  return (
    <div className="platform-view osint-workspace">
      <WorkspaceHeader
        eyebrow="Public-source enrichment"
        title="OSINT Workspace"
        description="Run explicit public lookups, inspect provenance, and decide what becomes investigation evidence."
        actions={<button type="button" onClick={onOpenGraph}><GitBranch size={14} /> Open graph</button>}
      />

      <div className="osint-grid">
        <section className="platform-section osint-query-panel">
          <div className="platform-section-heading">
            <div><span className="platform-eyebrow">New lookup</span><h2>Query a public source</h2></div>
            <ShieldCheck size={18} />
          </div>
          <form onSubmit={runLookup} className="osint-form">
            <label>Input type
              <select value={type} onChange={(event) => setType(event.target.value as LookupType)}>
                {LOOKUP_TYPES.map((item) => <option key={item.id} value={item.id}>{item.label}{item.available ? "" : " - adapter required"}</option>)}
              </select>
            </label>
            <label>Value
              <input value={value} onChange={(event) => setValue(event.target.value)} placeholder="example.org, 1.1.1.1, or analyst@example.org" />
            </label>
            <div className="osint-form-actions">
              <button type="submit" disabled={loading}>{loading ? <><Search size={14} /> Looking up…</> : <><Search size={14} /> Run lookup</>}</button>
              {loading && <button type="button" className="platform-secondary-btn" onClick={() => abortRef.current?.abort()}><Square size={13} /> Cancel</button>}
            </div>
          </form>
          <p className="platform-footnote">DNS, certificate transparency, and RDAP requests may contact public services. Results stay drafts until you add them to the graph.</p>
          {error && <div className="platform-inline-error"><AlertTriangle size={15} /> {error}</div>}
        </section>

        <section className="platform-section osint-history-panel">
          <div className="platform-section-heading">
            <div><span className="platform-eyebrow">SQLite history</span><h2>Recent queries</h2></div>
            <History size={18} />
          </div>
          {history.length === 0 ? <EmptyState title="No lookup history" description="Completed queries will appear here after the first run." /> : (
            <div className="osint-history-list">
              {history.map((item) => (
                <button type="button" key={item.id} className={result?.query_id === item.id ? "active" : ""} onClick={() => setResult(resultFromHistory(item))}>
                  <span><strong>{item.value}</strong><small>{item.kind} · {formatDate(item.created_at)}</small></span>
                  {item.promoted ? <CheckCircle2 size={15} aria-label="In graph" /> : <Database size={15} aria-label="Stored draft" />}
                </button>
              ))}
            </div>
          )}
        </section>
      </div>

      <section className="platform-section osint-results">
        <div className="platform-section-heading">
          <div><span className="platform-eyebrow">Review before promotion</span><h2>Lookup results</h2></div>
          {result && <span className={`platform-status ${result.promoted ? "success" : ""}`}>{result.promoted ? "In graph" : "Draft"}</span>}
        </div>
        {!result ? <EmptyState title="No result selected" description="Run a lookup or select a stored query to inspect its findings." /> : (
          <>
            <div className="osint-result-summary">
              <div><span>Input</span><strong>{result.value}</strong></div>
              <div><span>Detected type</span><strong>{result.kind}</strong></div>
              <div><span>Findings</span><strong>{result.findings.length}</strong></div>
              <div><span>Collection errors</span><strong>{result.errors.length}</strong></div>
            </div>
            {result.findings.length === 0 ? <EmptyState title="No public findings" description="The lookup completed without producing a verified finding. Nothing synthetic was added." /> : (
              <div className="platform-table-wrap"><table className="platform-table"><thead><tr><th>Source</th><th>Type</th><th>Value</th><th>Detail</th></tr></thead><tbody>
                {result.findings.map((finding, index) => <tr key={`${finding.source}-${finding.type}-${index}`}><td>{finding.source}</td><td>{finding.type}</td><td className="platform-mono">{finding.value}</td><td>{finding.detail}</td></tr>)}
              </tbody></table></div>
            )}
            {result.errors.length > 0 && <div className="osint-errors"><strong>Partial collection errors</strong>{result.errors.map((item) => <span key={item}>{item}</span>)}</div>}
            <div className="osint-result-actions">
              <button type="button" onClick={() => void promote()} disabled={promoting || result.promoted || result.findings.length === 0}><GitBranch size={14} /> {result.promoted ? "Already in graph" : promoting ? "Adding…" : "Add verified findings to graph"}</button>
              {result.promoted && <button type="button" className="platform-secondary-btn" onClick={onOpenGraph}>Inspect graph</button>}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
