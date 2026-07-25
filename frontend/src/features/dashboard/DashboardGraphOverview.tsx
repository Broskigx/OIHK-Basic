import { ArrowUpRight, CircleDot, GitFork, Network } from "lucide-react";
import { lazy, Suspense, useState } from "react";
import { GraphModeTabs } from "../graph/GraphModeTabs";
import { type GraphViewMode } from "../graph/graphModes";
import type { GraphAnalytics, GraphNode, GraphRead } from "../../types";

const GraphView = lazy(() =>
  import("../../components/GraphView").then((module) => ({ default: module.GraphView })),
);

export function DashboardGraphOverview({
  graph,
  analytics,
  selectedNode,
  onSelectNode,
  onOpenGraph,
}: {
  graph: GraphRead;
  analytics: GraphAnalytics | null;
  selectedNode: GraphNode | null;
  onSelectNode: (node: GraphNode) => void;
  onOpenGraph: () => void;
}) {
  const [viewMode, setViewMode] = useState<GraphViewMode>("network");

  return (
    <section className="platform-dashboard-graph" aria-label="Inteligencia de relaciones">
      <div className="platform-dashboard-graph-heading">
        <div>
          <span className="platform-eyebrow">Relationship intelligence</span>
          <h2>Mapa operativo del caso</h2>
          <p>Explora la red real del expediente desde distintos modelos visuales sin salir del Dashboard.</p>
        </div>
        <div className="platform-dashboard-graph-summary" aria-label="Resumen del grafo">
          <span><CircleDot size={14} /><strong>{graph.nodes.length}</strong> entidades</span>
          <span><GitFork size={14} /><strong>{graph.edges.length}</strong> vínculos</span>
          <span><Network size={14} /><strong>{analytics?.component_count ?? "—"}</strong> componentes</span>
        </div>
      </div>

      <GraphModeTabs value={viewMode} onChange={setViewMode} compact />

      <div className="platform-dashboard-graph-stage">
        <Suspense fallback={<div className="platform-module-loading">Cargando motor de grafo…</div>}>
          <GraphView
            graph={graph}
            viewMode={viewMode}
            selectedNodeId={selectedNode?.id}
            compact
            onSelectNode={onSelectNode}
            onNodeClick={(node) => onSelectNode(node)}
            onNodeContextMenu={(node) => onSelectNode(node)}
          />
        </Suspense>
        <div className="platform-dashboard-graph-status">
          {selectedNode ? (
            <>
              <i aria-hidden="true" />
              <span><strong>{selectedNode.label}</strong><small>{selectedNode.type} · {Math.round(selectedNode.confidence * 100)}% confianza</small></span>
            </>
          ) : (
            <span><strong>Vista general</strong><small>Selecciona un nodo para centrar la vista de conexiones.</small></span>
          )}
          <button type="button" onClick={onOpenGraph}>
            Abrir workspace
            <ArrowUpRight size={14} />
          </button>
        </div>
      </div>
    </section>
  );
}
