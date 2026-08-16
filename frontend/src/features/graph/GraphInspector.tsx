import { ArrowDownLeft, ArrowUpRight, ExternalLink, FileText, Loader2, Network, Tag, X } from "lucide-react";
import { useEffect, useState } from "react";
import { getEntityDossier } from "../../api";
import { safeExternalHref } from "../../lib/safeUrl";
import type { EntityDossier, GraphNode } from "../../types";

function dateLabel(value: string | null | undefined): string {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not recorded" : date.toLocaleString();
}

export function GraphInspector({ node, onClose, onOpenNode, onOpenRecord }: {
  node: GraphNode;
  onClose: () => void;
  onOpenNode: (node: GraphNode) => void;
  onOpenRecord: () => void;
}) {
  const [dossier, setDossier] = useState<EntityDossier | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setDossier(null);
    setError("");
    if (node.id.startsWith("prepared-")) {
      setLoading(false);
      return () => { cancelled = true; };
    }
    setLoading(true);
    getEntityDossier(node.id)
      .then((result) => { if (!cancelled) setDossier(result); })
      .catch((cause) => { if (!cancelled) setError(cause instanceof Error ? cause.message : "Could not load entity provenance"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [node.id]);

  const activeNode = dossier?.entity ?? node;
  const properties = Object.entries(activeNode.properties ?? {});

  return (
    <aside className="graph-inspector" aria-label="Selected entity inspector">
      <header>
        <div><span>Entity inspector</span><strong title={activeNode.label}>{activeNode.label}</strong></div>
        <button type="button" onClick={onClose} aria-label="Close inspector" title="Close inspector"><X size={15} /></button>
      </header>
      <div className="graph-inspector-scroll">
        <dl className="graph-inspector-summary">
          <div><dt>Type</dt><dd>{activeNode.type}</dd></div>
          <div><dt>Identifier</dt><dd title={activeNode.id}>{activeNode.id}</dd></div>
          {activeNode.value && <div><dt>Value</dt><dd title={activeNode.value}>{activeNode.value}</dd></div>}
          <div><dt>Confidence</dt><dd>{Math.round(activeNode.confidence * 100)}%</dd></div>
          <div><dt>First seen</dt><dd>{dateLabel(dossier?.first_seen ?? activeNode.created_at)}</dd></div>
          <div><dt>Last seen</dt><dd>{dateLabel(dossier?.last_seen ?? activeNode.updated_at)}</dd></div>
        </dl>

        <section>
          <h3><Tag size={13} />Properties</h3>
          {properties.length === 0 ? <p>No stored properties.</p> : (
            <dl className="graph-inspector-properties">
              {properties.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}
            </dl>
          )}
          {activeNode.notes && <p className="graph-inspector-notes">{activeNode.notes}</p>}
        </section>

        <section>
          <h3><Network size={13} />Relationships {dossier ? `(${dossier.connections.length})` : ""}</h3>
          {loading ? <p className="graph-inspector-loading"><Loader2 size={13} className="spin" />Loading relationships…</p> : error ? <p className="graph-inspector-error">{error}</p> : dossier?.connections.length ? (
            <ul className="graph-inspector-relations">
              {dossier.connections.map((connection) => (
                <li key={connection.relationship_id}>
                  <button type="button" onClick={() => onOpenNode(connection.entity)}>
                    {connection.direction === "outgoing" ? <ArrowUpRight size={13} /> : <ArrowDownLeft size={13} />}
                    <span><strong>{connection.entity.label}</strong><small>{connection.relation.replace(/_/g, " ")} · {connection.entity.type}</small></span>
                  </button>
                </li>
              ))}
            </ul>
          ) : <p>No stored relationships.</p>}
        </section>

        <section>
          <h3><FileText size={13} />Sources / provenance {dossier ? `(${dossier.sources.length})` : ""}</h3>
          {loading ? <p className="graph-inspector-loading"><Loader2 size={13} className="spin" />Loading provenance…</p> : dossier?.sources.length ? (
            <ul className="graph-inspector-sources">
              {dossier.sources.map((source) => (
                <li key={source.source_id}>
                  {safeExternalHref(source.url) ? <a href={safeExternalHref(source.url)} target="_blank" rel="noopener noreferrer">{source.title}</a> : <strong>{source.title}</strong>}
                  <span>{source.kind} · reliability {Math.round(source.reliability * 100)}%</span>
                  {source.citation && <small>{source.citation}</small>}
                </li>
              ))}
            </ul>
          ) : <p>No linked sources. Provenance cannot be inferred.</p>}
        </section>

        <button type="button" className="graph-inspector-open-record" onClick={onOpenRecord}>
          <ExternalLink size={13} /> Open full entity record
        </button>
      </div>
    </aside>
  );
}
