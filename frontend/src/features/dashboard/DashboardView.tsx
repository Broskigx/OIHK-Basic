import React from "react";
import type { CaseRead, GraphNode, GraphRead } from "../../types";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";

type PlatformArea = "dashboard" | "investigations" | "entities" | "evidence" | "graph" | "tools" | "reports" | "timeline" | "settings";

export function DashboardView({
  cases, activeCase, graph, selectedNode, onNavigate, onNewCase,
}: {
  cases: CaseRead[];
  activeCase: CaseRead | undefined;
  graph: GraphRead;
  selectedNode: GraphNode | null;
  onNavigate: (area: PlatformArea) => void;
  onNewCase: () => void;
}) {
  const activeCases = cases.filter((c) => c.status === "active").length;
  const totalSources = graph.nodes.length;
  const totalEntities = graph.nodes.length;
  const totalRelationships = graph.edges.length;

  return (
    <div className="platform-view">
      <WorkspaceHeader
        eyebrow="OIHK Basic"
        title="Dashboard"
        description="Overview of your local investigations"
      />

      <div className="stat-row" style={{ marginBottom: "1.5rem" }}>
        <div className="stat-card">
          <div className="stat-value">{cases.length}</div>
          <div className="stat-label">Total Cases</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{activeCases}</div>
          <div className="stat-label">Active</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{totalEntities}</div>
          <div className="stat-label">Entities</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{totalRelationships}</div>
          <div className="stat-label">Relationships</div>
        </div>
      </div>

      <div className="card-grid">
        <div className="card">
          <h3 style={{ marginBottom: "0.75rem", fontSize: "1rem" }}>Recent Cases</h3>
          {cases.length === 0 ? (
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>
              No cases yet. Create your first investigation.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {cases.slice(0, 5).map((c) => (
                <div
                  key={c.id}
                  style={{ cursor: "pointer", padding: "0.5rem", borderRadius: "var(--radius-sm)", background: "var(--bg-tertiary)" }}
                  onClick={() => { onNavigate("investigations"); }}
                >
                  <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{c.title}</div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    {c.status} · {new Date(c.created_at).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          )}
          <button style={{ marginTop: "0.75rem", width: "100%" }} onClick={onNewCase}>
            New Investigation
          </button>
        </div>

        <div className="card">
          <h3 style={{ marginBottom: "0.75rem", fontSize: "1rem" }}>Quick Actions</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <button onClick={() => onNavigate("investigations")}>View Investigations</button>
            <button onClick={() => onNavigate("graph")}>Open Graph</button>
            <button onClick={() => onNavigate("tools")}>Forensic Tools</button>
          </div>
        </div>

        <div className="card">
          <h3 style={{ marginBottom: "0.75rem", fontSize: "1rem" }}>About OIHK Basic</h3>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
            OIHK Basic is a local-first investigation and OSINT platform. All data is stored
            locally using SQLite. No data is sent to external services unless you explicitly
            configure a search provider.
          </p>
        </div>
      </div>
    </div>
  );
}
