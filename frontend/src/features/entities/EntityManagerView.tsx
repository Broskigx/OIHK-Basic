import { ArrowRight, Link2, Plus, Save, Search, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getEntityDossier, renameEntity, updateEntityDetails } from "../../api";
import type { EntityDossier, GraphNode } from "../../types";
import { EmptyState } from "../../shared/ui/EmptyState";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";

type PropertyRow = { key: string; value: string };

function confidence(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function EntityInspector({
  node,
  onChanged,
  onOpenGraph,
  onError,
}: {
  node: GraphNode;
  onChanged: (node: GraphNode) => Promise<void>;
  onOpenGraph: () => void;
  onError: (message: string) => void;
}) {
  const [label, setLabel] = useState(node.label);
  const [notes, setNotes] = useState(node.notes ?? "");
  const [properties, setProperties] = useState<PropertyRow[]>(
    Object.entries(node.properties ?? {}).map(([key, value]) => ({ key, value: String(value) })),
  );
  const [dossier, setDossier] = useState<EntityDossier | null>(null);
  const [loadingDossier, setLoadingDossier] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoadingDossier(true);
    getEntityDossier(node.id)
      .then((result) => {
        if (!cancelled) setDossier(result);
      })
      .catch(() => {
        if (!cancelled) setDossier(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingDossier(false);
      });
    return () => {
      cancelled = true;
    };
  }, [node.id]);

  async function save() {
    setSaving(true);
    onError("");
    try {
      let updated = node;
      const nextLabel = label.trim();
      if (nextLabel && nextLabel !== node.label) {
        updated = await renameEntity(node.id, nextLabel);
      }
      const nextProperties: Record<string, string> = {};
      for (const row of properties) {
        const key = row.key.trim();
        if (key && row.value.trim()) nextProperties[key] = row.value.trim();
      }
      updated = await updateEntityDetails(updated.id, { properties: nextProperties, notes });
      await onChanged(updated);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not update entity");
    } finally {
      setSaving(false);
    }
  }

  return (
    <aside className="platform-entity-inspector">
      <div className="platform-section-heading">
        <div>
          <span className="platform-eyebrow">Entity inspector</span>
          <h2>{node.label}</h2>
        </div>
        <span className="platform-confidence">{confidence(node.confidence)}</span>
      </div>
      <div className="platform-entity-meta">
        <span>{node.type}</span>
        <span>{node.source_ids.length} source{node.source_ids.length === 1 ? "" : "s"}</span>
      </div>

      <label>
        Display label
        <input value={label} onChange={(event) => setLabel(event.target.value)} />
      </label>
      <label>
        Analyst notes
        <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={4} />
      </label>

      <div className="platform-property-editor">
        <div className="platform-inline-heading">
          <strong>Properties</strong>
          <button
            type="button"
            className="platform-text-button"
            onClick={() => setProperties((current) => [...current, { key: "", value: "" }])}
          >
            <Plus size={13} />
            Add
          </button>
        </div>
        {properties.length === 0 && <p className="platform-muted">No custom properties recorded.</p>}
        {properties.map((row, index) => (
          <div className="platform-property-row" key={index}>
            <input
              aria-label="Property name"
              value={row.key}
              onChange={(event) =>
                setProperties((current) =>
                  current.map((item, itemIndex) => itemIndex === index ? { ...item, key: event.target.value } : item),
                )
              }
              placeholder="Property"
            />
            <input
              aria-label="Property value"
              value={row.value}
              onChange={(event) =>
                setProperties((current) =>
                  current.map((item, itemIndex) => itemIndex === index ? { ...item, value: event.target.value } : item),
                )
              }
              placeholder="Value"
            />
            <button
              type="button"
              className="platform-icon-button"
              onClick={() => setProperties((current) => current.filter((_, itemIndex) => itemIndex !== index))}
              aria-label="Remove property"
            >
              <Trash2 size={13} />
            </button>
          </div>
        ))}
      </div>

      <div className="platform-inspector-actions">
        <button type="button" className="platform-primary" onClick={save} disabled={saving}>
          <Save size={14} />
          {saving ? "Saving…" : "Save changes"}
        </button>
        <button type="button" onClick={onOpenGraph}>
          Open in graph
          <ArrowRight size={14} />
        </button>
      </div>

      <div className="platform-dossier">
        <div className="platform-inline-heading">
          <strong>Relationships</strong>
          <Link2 size={14} />
        </div>
        {loadingDossier && <p className="platform-muted">Loading dossier…</p>}
        {!loadingDossier && dossier?.connections.length === 0 && (
          <p className="platform-muted">No relationships recorded.</p>
        )}
        {dossier?.connections.slice(0, 8).map((connection) => (
          <div className="platform-dossier-row" key={connection.relationship_id}>
            <span>{connection.relation.replace(/_/g, " ")}</span>
            <strong>{connection.entity.label}</strong>
            <small>{confidence(connection.confidence)}</small>
          </div>
        ))}
      </div>
    </aside>
  );
}
export function EntityManagerView({
  nodes,
  selectedNode,
  onSelectNode,
  onRefresh,
  onOpenGraph,
  onError,
}: {
  nodes: GraphNode[];
  selectedNode: GraphNode | null;
  onSelectNode: (node: GraphNode) => void;
  onRefresh: () => Promise<void>;
  onOpenGraph: () => void;
  onError: (message: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const types = useMemo(() => [...new Set(nodes.map((node) => node.type))].sort(), [nodes]);
  const filtered = useMemo(
    () =>
      nodes.filter((node) => {
        const matchesQuery = node.label.toLowerCase().includes(query.trim().toLowerCase());
        return matchesQuery && (typeFilter === "all" || node.type === typeFilter);
      }),
    [nodes, query, typeFilter],
  );

  const active = selectedNode && nodes.some((node) => node.id === selectedNode.id)
    ? nodes.find((node) => node.id === selectedNode.id) ?? null
    : filtered[0] ?? null;

  return (
    <div className="platform-view">
      <WorkspaceHeader
        eyebrow="Investigation workspace"
        title="Entities"
        description="Review typed intelligence objects, confidence, provenance, properties, notes, and relationships."
      />
      {nodes.length === 0 ? (
        <EmptyState
          title="No entities collected"
          description="Run an authorized investigation, ingest a source, or add an entity from the graph workspace."
          action={<button onClick={onOpenGraph}>Open graph workspace</button>}
        />
      ) : (
        <div className="platform-entity-layout">
          <section className="platform-table-panel">
            <div className="platform-filterbar">
              <label className="platform-search">
                <Search size={14} />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search entities"
                />
              </label>
              <select aria-label="Entity type" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
                <option value="all">All types</option>
                {types.map((type) => <option key={type} value={type}>{type}</option>)}
              </select>
              <span>{filtered.length} shown</span>
            </div>
            <div className="platform-table-wrap">
              <table className="platform-table">
                <thead>
                  <tr>
                    <th>Entity</th>
                    <th>Type</th>
                    <th>Confidence</th>
                    <th>Sources</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((node) => (
                    <tr
                      key={node.id}
                      className={node.id === active?.id ? "selected" : ""}
                      onClick={() => onSelectNode(node)}
                    >
                      <td><strong>{node.label}</strong></td>
                      <td><span className="platform-status">{node.type}</span></td>
                      <td>{confidence(node.confidence)}</td>
                      <td>{node.source_ids.length}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          {active && (
            <EntityInspector
              key={active.id}
              node={active}
              onChanged={async (updated) => {
                onSelectNode(updated);
                await onRefresh();
              }}
              onOpenGraph={onOpenGraph}
              onError={onError}
            />
          )}
        </div>
      )}
    </div>
  );
}
