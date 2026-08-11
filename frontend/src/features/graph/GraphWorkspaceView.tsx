import { Filter, RotateCcw } from "lucide-react";
import { lazy, Suspense } from "react";
import type { FormEvent } from "react";
import type { GraphAnalytics, GraphNode, GraphRead, ManualEntityForm } from "../../types";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import { GraphInspector } from "./GraphInspector";

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
  manualEntity,
  onManualEntityChange,
  onAddEntity,
  onSelectNode,
  onOpenNode,
  onCloseInspector,
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
  manualEntity: ManualEntityForm;
  onManualEntityChange: (patch: Partial<ManualEntityForm>) => void;
  onAddEntity: (event: FormEvent) => void;
  onSelectNode: (node: GraphNode | null) => void;
  onOpenNode: (node: GraphNode) => void;
  onCloseInspector: () => void;
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
  const inspectedNode = openedNode ?? selectedNode;
  const selectAndInspect = (node: GraphNode | null) => {
    onSelectNode(node);
    if (node) onOpenNode(node);
    else onCloseInspector();
  };

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
              Auto layout
            </button>
          </>
        }
      />
      <form className="platform-entity-create" onSubmit={onAddEntity}>
        <label>
          <span>New entity</span>
          <input
            aria-label="New entity label"
            value={manualEntity.label}
            onChange={(event) => onManualEntityChange({ label: event.target.value })}
            placeholder="Name, alias, URL, email, evidence…"
            maxLength={500}
          />
        </label>
        <label>
          <span>Type</span>
          <select
            aria-label="New entity type"
            value={manualEntity.type}
            onChange={(event) => onManualEntityChange({ type: event.target.value })}
          >
            {["name", "handle", "email", "url", "phone", "organization", "source", "note"].map((type) => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Confidence</span>
          <input
            aria-label="New entity confidence"
            min="0"
            max="1"
            step="0.01"
            type="number"
            value={manualEntity.confidence}
            onChange={(event) => onManualEntityChange({ confidence: Number(event.target.value) })}
          />
        </label>
        <label>
          <span>Relationship</span>
          <input
            aria-label="New entity relationship"
            value={manualEntity.relation_label}
            onChange={(event) => onManualEntityChange({ relation_label: event.target.value })}
            placeholder={selectedNode ? `Link to ${selectedNode.label}` : "Select a node to link"}
            maxLength={200}
          />
        </label>
        <button
          type="submit"
          className="platform-primary"
          disabled={!caseId || !manualEntity.label.trim()}
        >
          Add to graph
        </button>
      </form>
      <div className={inspectedNode ? "platform-graph-layout inspected" : "platform-graph-layout"}>
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
              onSelectNode={selectAndInspect}
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
        {inspectedNode && <GraphInspector node={inspectedNode} onClose={onCloseInspector} onOpenNode={onOpenNode} onOpenRecord={onOpenEntityManager} />}
      </div>
    </div>
  );
}
