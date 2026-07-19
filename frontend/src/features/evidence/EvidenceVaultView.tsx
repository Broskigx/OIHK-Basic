import React from "react";
import type { SourceRead, TargetPhoto, CustodyReport } from "../../types";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import { EmptyState } from "../../shared/ui/EmptyState";

export function EvidenceVaultView({
  caseId, sources, photos, custody, onRefresh,
}: {
  caseId: string | null;
  sources: SourceRead[];
  photos: TargetPhoto[];
  custody: CustodyReport | null;
  onRefresh: () => void;
}) {
  if (!caseId) {
    return (
      <div className="platform-view">
        <EmptyState title="No active case" description="Open an investigation to view evidence." />
      </div>
    );
  }

  return (
    <div className="platform-view">
      <WorkspaceHeader
        eyebrow="Evidence Vault"
        title="Evidence"
        description={`${sources.length} sources, ${photos.length} photos`}
      >
        <button style={{ marginTop: "0.5rem" }} onClick={onRefresh}>Refresh</button>
      </WorkspaceHeader>

      <div className="stat-row" style={{ marginBottom: "1.5rem" }}>
        <div className="stat-card">
          <div className="stat-value">{sources.length}</div>
          <div className="stat-label">Sources</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{photos.length}</div>
          <div className="stat-label">Photos</div>
        </div>
        {custody && (
          <>
            <div className="stat-card">
              <div className="stat-value">{custody.sealed_count}</div>
              <div className="stat-label">Seals</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">
                <span className={`badge badge-${custody.intact ? "success" : "danger"}`}>
                  {custody.intact ? "Intact" : "Broken"}
                </span>
              </div>
              <div className="stat-label">Custody Chain</div>
            </div>
          </>
        )}
      </div>

      {sources.length > 0 && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h3 style={{ fontSize: "0.9rem", marginBottom: "0.75rem" }}>Sources</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Kind</th>
                <th>Reliability</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.id}>
                  <td style={{ fontWeight: 500, maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis" }}>{s.title}</td>
                  <td><span className="badge badge-info">{s.kind}</span></td>
                  <td>{(s.reliability * 100).toFixed(0)}%</td>
                  <td style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    {new Date(s.collected_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {photos.length > 0 && (
        <div className="card">
          <h3 style={{ fontSize: "0.9rem", marginBottom: "0.75rem" }}>Photos</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Type</th>
                <th>SHA256</th>
                <th>Size</th>
              </tr>
            </thead>
            <tbody>
              {photos.map((p) => (
                <tr key={p.id}>
                  <td>{p.filename}</td>
                  <td>{p.content_type}</td>
                  <td style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)" }}>{p.sha256.slice(0, 16)}…</td>
                  <td>{(p.size_bytes / 1024).toFixed(1)} KB</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {sources.length === 0 && photos.length === 0 && (
        <EmptyState title="No evidence yet" description="Evidence appears here as you collect sources." />
      )}
    </div>
  );
}
