import { Filter, RotateCcw } from "lucide-react";
import { lazy, Suspense } from "react";
import type { GraphAnalytics, GraphNode, GraphRead } from "../../types";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";

const GraphPanel = lazy(() =>
  import("../../components/GraphPanel").then((module) => ({ default: module.GraphPanel })),
);

export function GraphWorkspaceView({
  graph,
  analytics,
  selectedNode,
  openedNode,
  zoom,
  layoutVersion,
  showFilters,
  expanding,
  caseId,
  onSelectNode,
  onOpenNode,
  onExpandNode,
  onEnrichNode,
  onRunTransform,
  onRunAdhocMachine,
  onRunSavedMachine,
  onImportCsv,
  onGraphChanged,
  onToggleFilters,
  onResetLayout,
  onOpenEntityManager,
  onError,
}: {
  graph: GraphRead;
  analytics: GraphAnalytics | null;
  selectedNode: GraphNode | null;
  openedNode: GraphNode | null;
  zoom: number;
  layoutVersion: number;
  showFilters: boolean;
  expanding: boolean;
  caseId: string;
  onSelectNode: (node: GraphNode | null) => void;
  onOpenNode: (node: GraphNode) => void;
  onExpandNode: (node: GraphNode) => void;
  onEnrichNode: (node: GraphNode) => void;
  onRunTransform: (transformId: string, node: GraphNode) => void;
  onRunAdhocMachine: (transformIds: string[], node: GraphNode) => void;
  onRunSavedMachine: (machineId: string, node: GraphNode) => void;
  onImportCsv: (csv: string) => void;
  onGraphChanged: () => Promise<void>;
  onToggleFilters: () => void;
  onResetLayout: () => void;
  onOpenEntityManager: () => void;
  onError: (message: string) => void;
}) {
  return (
    <div className="platform-view platform-graph-view">
      <WorkspaceHeader
        eyebrow="Investigation workspace"
        title="Graph"
        description="Explore evidence-backed entities and relationships, run transforms, and inspect graph analytics."
        actions={
          <>
            <button type="button" className={showFilters ? "active" : ""} onClick={onToggleFilters}>
              <Filter size={14} />
              Filters
            </button>
            <button type="button" onClick={onResetLayout}>
              <RotateCcw size={14} />
              Reset layout
            </button>
          </>
        }
      />
      <div className={openedNode ? "platform-graph-layout inspected" : "platform-graph-layout"}>
        <section className="platform-graph-canvas">
          <Suspense fallback={<div className="platform-module-loading">Loading graph engine…</div>}>
            <GraphPanel
              graph={graph}
              zoom={zoom}
              layoutVersion={layoutVersion}
              showFilters={showFilters}
              selectedNode={selectedNode}
              graphAnalytics={analytics}
              expanding={expanding}
              caseId={caseId}
              onSelectNode={onSelectNode}
              onOpenNode={onOpenNode}
              onExpandNode={onExpandNode}
              onEnrichNode={onEnrichNode}
              onConnectNode={onSelectNode}
              onRunTransform={onRunTransform}
              onRunAdhocMachine={onRunAdhocMachine}
              onRunSavedMachine={onRunSavedMachine}
              onImportCsv={onImportCsv}
              onGraphChanged={onGraphChanged}
              onError={onError}
            />
          </Suspense>
        </section>
        {openedNode && (
          <aside className="platform-graph-inspector">
            <span className="platform-eyebrow">Selected entity</span>
            <h2>{openedNode.label}</h2>
            <div className="platform-entity-meta">
              <span>{openedNode.type}</span>
              <span>{Math.round(openedNode.confidence * 100)}% confidence</span>
            </div>
            {openedNode.notes && <p>{openedNode.notes}</p>}
            <dl className="platform-property-list">
              {Object.entries(openedNode.properties ?? {}).map(([key, value]) => (
                <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>
              ))}
              <div><dt>Sources</dt><dd>{openedNode.source_ids.length}</dd></div>
            </dl>
            <button type="button" className="platform-primary platform-wide" onClick={onOpenEntityManager}>
              Open full entity record
            </button>
          </aside>
        )}
      </div>
    </div>
  );
}
