import React, { useState } from "react";
import type { GraphNode } from "../../types";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import { EmptyState } from "../../shared/ui/EmptyState";

export function EntityManagerView({
  nodes, onRefresh, onOpenGraph, onError,
}: {
  nodes: GraphNode[];
  onRefresh: () => void;
  onOpenGraph: () => void;
  onError: (msg: string) => void;
}) {
  const [search, setSearch] = useState("");

  const filtered = search
    ? nodes.filter((n) => n.label.toLowerCase().includes(search.toLowerCase()) || n.type.includes(search.toLowerCase()))
    : nodes;

  const typeCounts: Record<string, number> = {};
  for (const n of nodes) {
    typeCounts[n.type] = (typeCounts[n.type] || 0) + 1;
  }

  return (
    <div className="platform-view">
      <WorkspaceHeader
        eyebrow="Entity Management"
        title="Entity Manager"
        description={`${nodes.length} total entities across all types.`}
      >
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
          <button onClick={onRefresh}>Refresh</button>
          <button onClick={onOpenGraph}>Open Graph</button>
        </div>
      </WorkspaceHeader>

      <div className="stat-row" style={{ marginBottom: "1rem" }}>
        {Object.entries(typeCounts).slice(0, 8).map(([type, count]) => (
          <div key={type} className="stat-card" style={{ minWidth: "auto", padding: "0.5rem 1rem" }}>
            <div className="stat-label">{type}</div>
            <div className="stat-value" style={{ fontSize: "1.2rem" }}>{count}</div>
          </div>
        ))}
      </div>

      <div className="form-group" style={{ maxWidth: 400 }}>
        <input
          type="text"
          placeholder="Search entities…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {filtered.length === 0 ? (
        <EmptyState title="No entities found" description={search ? "Try a different search term." : "No entities in this case yet."} />
      ) : (
        <div className="card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Label</th>
                <th>Type</th>
                <th>Confidence</th>
                <th>Sources</th>
                <th>First Seen</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((node) => (
                <tr key={node.id}>
                  <td style={{ fontWeight: 500 }}>{node.label}</td>
                  <td><span className="badge badge-info">{node.type}</span></td>
                  <td>{(node.confidence * 100).toFixed(0)}%</td>
                  <td>{node.source_ids.length}</td>
                  <td style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    {node.created_at ? new Date(node.created_at).toLocaleDateString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
