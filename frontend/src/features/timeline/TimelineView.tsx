import React from "react";
import type { AuditEvent, SourceRead } from "../../types";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import { EmptyState } from "../../shared/ui/EmptyState";

export function TimelineView({
  auditEvents, sources,
}: {
  auditEvents: AuditEvent[];
  sources: SourceRead[];
}) {
  const items = [
    ...auditEvents.map((e) => ({
      id: `audit-${e.id}`,
      date: e.created_at,
      title: e.action,
      detail: e.actor,
      type: "audit" as const,
    })),
    ...sources.map((s) => ({
      id: `source-${s.id}`,
      date: s.collected_at,
      title: s.title,
      detail: s.kind,
      type: "source" as const,
    })),
  ].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

  return (
    <div className="platform-view">
      <WorkspaceHeader
        eyebrow="Chronological Activity"
        title="Timeline"
        description={`${items.length} events in chronological order.`}
      />

      {items.length === 0 ? (
        <EmptyState title="No events yet" description="Timeline events appear as you work." />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {items.map((item) => (
            <div key={item.id} className="card" style={{ padding: "0.75rem 1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <span style={{ fontWeight: 500, fontSize: "0.9rem" }}>{item.title}</span>
                  {item.detail && (
                    <span style={{ color: "var(--text-secondary)", fontSize: "0.8rem", marginLeft: "0.5rem" }}>
                      — {item.detail}
                    </span>
                  )}
                </div>
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <span className={`badge badge-${item.type === "audit" ? "info" : "success"}`}>
                    {item.type}
                  </span>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                    {new Date(item.date).toLocaleString()}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
