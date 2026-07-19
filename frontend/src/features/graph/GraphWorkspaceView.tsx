import React from "react";
import type { GraphRead, GraphAnalytics, GraphNode } from "../../types";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import { EmptyState } from "../../shared/ui/EmptyState";

export function GraphWorkspaceView({
  graph, analytics, selectedNode, caseId, onRefresh, onOpenEntityManager, onError,
}: {
  graph: GraphRead;
  analytics: GraphAnalytics | null;
  selectedNode: GraphNode | null;
  caseId: string | null;
  onRefresh: () => void;
  onOpenEntityManager: () => void;
  onError: (msg: string) => void;
}) {
  if (!caseId) {
    return (
      <div className="platform-view">
        <EmptyState title="No active case" description="Open an investigation to view the graph." />
      </div>
    );
  }

  const nodeCount = graph.nodes.length;
  const edgeCount = graph.edges.length;

  return (
    <div className="platform-view">
      <WorkspaceHeader
        eyebrow="Intelligence Graph"
        title="Entity Graph"
        description="Visualize entities and relationships in your investigation."
      >
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
          <button onClick={onRefresh}>Refresh</button>
          <button onClick={onOpenEntityManager}>Entity Manager</button>
        </div>
      </WorkspaceHeader>

      <div className="stat-row" style={{ marginBottom: "1.5rem" }}>
        <div className="stat-card">
          <div className="stat-value">{nodeCount}</div>
          <div className="stat-label">Entities</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{edgeCount}</div>
          <div className="stat-label">Relationships</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{analytics ? analytics.density.toFixed(3) : "—"}</div>
          <div className="stat-label">Density</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{analytics ? analytics.component_count : "—"}</div>
          <div className="stat-label">Components</div>
        </div>
      </div>

      {analytics && analytics.top_hubs.length > 0 && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h3 style={{ fontSize: "0.9rem", marginBottom: "0.5rem" }}>Top Hubs</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Entity</th>
                <th>Type</th>
                <th>Degree</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {analytics.top_hubs.slice(0, 10).map((hub) => (
                <tr key={hub.entity_id}>
                  <td>{hub.label}</td>
                  <td><span className="badge badge-info">{hub.type}</span></td>
                  <td>{hub.degree}</td>
                  <td>{hub.score.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card">
        <h3 style={{ fontSize: "0.9rem", marginBottom: "0.75rem" }}>Node List</h3>
        {nodeCount === 0 ? (
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>
            No entities in this case yet. Add data through investigations or manual entry.
          </p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Label</th>
                <th>Type</th>
                <th>Confidence</th>
                <th>Sources</th>
              </tr>
            </thead>
            <tbody>
              {graph.nodes.slice(0, 50).map((node) => (
                <tr key={node.id}>
                  <td style={{ fontWeight: 500 }}>{node.label}</td>
                  <td><span className="badge badge-info">{node.type}</span></td>
                  <td>{(node.confidence * 100).toFixed(0)}%</td>
                  <td>{node.source_ids.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
