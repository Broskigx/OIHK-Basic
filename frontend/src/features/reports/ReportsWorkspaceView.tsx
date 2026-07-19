import React from "react";
import type { CaseRead, GraphRead, SourceRead, CustodyReport } from "../../types";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import { EmptyState } from "../../shared/ui/EmptyState";
import { reportUrl } from "../../api";

export function ReportsWorkspaceView({
  activeCase, graph, sources, custody, onDownloadMarkdown,
}: {
  activeCase: CaseRead;
  graph: GraphRead;
  sources: SourceRead[];
  custody: CustodyReport | null;
  onDownloadMarkdown: () => void;
}) {
  return (
    <div className="platform-view">
      <WorkspaceHeader
        eyebrow="Investigation Report"
        title={`Report: ${activeCase.title}`}
        description="Machine-assisted markdown report of the current investigation."
      >
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
          <button className="primary" onClick={onDownloadMarkdown}>Download Markdown</button>
          <button onClick={() => window.open(reportUrl(activeCase.id), "_blank")}>View in Browser</button>
        </div>
      </WorkspaceHeader>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <h3 style={{ marginBottom: "1rem" }}>Report Preview</h3>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
          {`# ${activeCase.title}

Status: ${activeCase.status}
Legal basis: ${activeCase.legal_basis}

## Scope
${activeCase.scope_statement}

## Sources (${sources.length})
${sources.map((s) => `- ${s.title} (${s.kind}, reliability ${(s.reliability * 100).toFixed(0)}%)`).join("\n")}

## Entities (${graph.nodes.length})
${graph.nodes.map((n) => `- ${n.type}: ${n.label} (confidence ${(n.confidence * 100).toFixed(0)}%)`).join("\n")}

## Relationships (${graph.edges.length})
${graph.edges.map((e) => `- ${e.source} — ${e.label} → ${e.target}`).join("\n")}

## Review note
This report is machine-assisted. Verify identities, context, and legal basis before external use.`}
        </div>
      </div>
    </div>
  );
}
