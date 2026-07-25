import { ArrowRight, Database, ExternalLink, Search } from "lucide-react";
import { useMemo, useState } from "react";
import type { CaseRead, SourceRead } from "../../types";
import { EmptyState } from "../../shared/ui/EmptyState";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";

function date(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function DataSourcesView({
  activeCase,
  sources,
  onOpenEvidence,
  onOpenInvestigations,
}: {
  activeCase?: CaseRead;
  sources: SourceRead[];
  onOpenEvidence: () => void;
  onOpenInvestigations: () => void;
}) {
  const [query, setQuery] = useState("");
  const visible = useMemo(() => {
    const value = query.trim().toLowerCase();
    if (!value) return sources;
    return sources.filter((source) => [source.title, source.kind, source.citation, source.url ?? ""].some((field) => field.toLowerCase().includes(value)));
  }, [query, sources]);

  function openExternal(url: string) {
    let parsed: URL;
    try {
      parsed = new URL(url);
    } catch {
      return;
    }
    if (!['http:', 'https:'].includes(parsed.protocol)) return;
    if (window.confirm(`Open this external source in your browser?\n\n${parsed.href}`)) {
      window.open(parsed.href, "_blank", "noopener,noreferrer");
    }
  }

  return (
    <div className="platform-view">
      <WorkspaceHeader
        eyebrow="Provenance registry"
        title="Data Sources"
        description="A searchable inventory of sources actually collected for the active investigation."
        actions={activeCase ? <button type="button" onClick={onOpenEvidence}>Open Evidence Lab <ArrowRight size={14} /></button> : undefined}
      />
      {!activeCase ? (
        <EmptyState title="No active investigation" description="Choose an investigation to inspect its collected sources." action={<button onClick={onOpenInvestigations}>View investigations</button>} />
      ) : sources.length === 0 ? (
        <EmptyState title="No sources collected" description="Run an authorized query or ingest evidence to populate this registry." action={<button onClick={onOpenEvidence}>Open Evidence Lab</button>} />
      ) : (
        <section className="platform-section">
          <div className="platform-table-tools">
            <label><Search size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search title, type or citation" /></label>
            <span>{visible.length} of {sources.length} sources</span>
          </div>
          <div className="platform-table-wrap">
            <table className="platform-table">
              <thead><tr><th>Source</th><th>Type</th><th>Reliability</th><th>Collected</th><th>Reference</th></tr></thead>
              <tbody>{visible.map((source) => (
                <tr key={source.id}>
                  <td><strong><Database size={14} /> {source.title}</strong><small>{source.license || "Terms not recorded"}</small></td>
                  <td>{source.kind}</td>
                  <td>{Math.round(source.reliability * 100)}%</td>
                  <td>{date(source.collected_at)}</td>
                  <td>{source.url ? <button type="button" className="platform-text-btn" onClick={() => openExternal(source.url!)}>Open source <ExternalLink size={12} /></button> : source.citation || "Internal record"}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
