import React from "react";
import type { CaseRead } from "../../types";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import { EmptyState } from "../../shared/ui/EmptyState";

export function InvestigationsView({
  cases, activeCase, onOpenCase, onNewCase, onOpenWorkspace,
}: {
  cases: CaseRead[];
  activeCase: CaseRead | undefined;
  onOpenCase: (id: string) => void;
  onNewCase: () => void;
  onOpenWorkspace: () => void;
}) {
  return (
    <div className="platform-view">
      <WorkspaceHeader
        eyebrow="OSINT Case Management"
        title="Investigations"
        description="Manage your OSINT investigations and cases."
      >
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
          <button className="primary" onClick={onNewCase}>New Investigation</button>
          {activeCase && <button onClick={onOpenWorkspace}>Open Workspace</button>}
        </div>
      </WorkspaceHeader>

      {cases.length === 0 ? (
        <EmptyState
          title="No investigations yet"
          description="Create your first investigation to get started."
          action={<button className="primary" onClick={onNewCase}>Create Investigation</button>}
        />
      ) : (
        <div className="investigation-list">
          {cases.map((c) => (
            <div
              key={c.id}
              className={`investigation-item ${activeCase?.id === c.id ? "active" : ""}`}
              onClick={() => onOpenCase(c.id)}
            >
              <h3>{c.title}</h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>
                {c.summary || c.scope_statement?.slice(0, 100)}...
              </p>
              <div className="meta">
                <span className={`badge badge-${c.status === "active" ? "success" : "info"}`}>{c.status}</span>
                <span>Legal: {c.legal_basis}</span>
                <span>Created: {new Date(c.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
