import { Network } from "lucide-react";
import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef } from "react";
import type { EngineWorkspaceState } from "../graph/types";
import {
  connectionsLayout,
  graphForView,
  hierarchyLayout,
  type GraphViewMode,
} from "../features/graph/graphModes";
import type { GraphNode, GraphRead } from "../types";
import IntelligenceCanvas, { type CanvasHandle } from "./IntelligenceCanvas";

export interface GraphViewHandle {
  fitToView: () => void;
  focusNode: (nodeId: string) => void;
  zoomBy: (factor: number) => void;
  resetLayout: () => void;
  togglePinned: (nodeId: string) => boolean;
  isPinned: (nodeId: string) => boolean;
  undo: () => boolean;
  redo: () => boolean;
  getWorkspace: () => EngineWorkspaceState | null;
  applyWorkspace: (workspace: EngineWorkspaceState) => void;
}

type Props = {
  graph: GraphRead;
  zoom?: number;
  layoutVersion?: number;
  selectedNodeId?: string;
  typeFilter?: string;
  compact?: boolean;
  viewMode?: GraphViewMode;
  workspace?: EngineWorkspaceState | null;
  onWorkspaceChange?: (workspace: EngineWorkspaceState) => void;
  onSelectNode?: (node: GraphNode) => void;
  onOpenNode?: (node: GraphNode) => void;
  onNodeClick?: (node: GraphNode, screen: { x: number; y: number }) => void;
  onNodeContextMenu?: (node: GraphNode, screen: { x: number; y: number }) => void;
};

export const GraphView = forwardRef<GraphViewHandle, Props>(function GraphView(props, ref) {
  const {
    graph,
    zoom = 1,
    layoutVersion = 0,
    selectedNodeId = "",
    typeFilter = "all",
    compact = false,
    viewMode = "network",
    workspace,
    onWorkspaceChange,
  } = props;
  const canvasRef = useRef<CanvasHandle>(null);
  const propsRef = useRef(props);
  propsRef.current = props;

  useImperativeHandle(ref, () => ({
    fitToView: () => canvasRef.current?.fitToView(),
    focusNode: (nodeId) => canvasRef.current?.focusNode(nodeId),
    zoomBy: (factor) => canvasRef.current?.zoomBy(factor),
    resetLayout: () => canvasRef.current?.resetLayout(),
    togglePinned: (nodeId) => canvasRef.current?.togglePinned(nodeId) ?? false,
    isPinned: (nodeId) => canvasRef.current?.isPinned(nodeId) ?? false,
    undo: () => canvasRef.current?.undo() ?? false,
    redo: () => canvasRef.current?.redo() ?? false,
    getWorkspace: () => canvasRef.current?.getWorkspace() ?? null,
    applyWorkspace: (state) => canvasRef.current?.applyWorkspace(state),
  }));

  const filtered = useMemo(() => {
    if (typeFilter === "all") return graph;
    const nodes = graph.nodes.filter((node) => node.type === typeFilter);
    const ids = new Set(nodes.map((node) => node.id));
    return { nodes, edges: graph.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)) };
  }, [graph, typeFilter]);

  const visible = useMemo(
    () => graphForView(filtered, viewMode, selectedNodeId),
    [filtered, selectedNodeId, viewMode],
  );

  useEffect(() => {
    canvasRef.current?.setZoom(zoom);
  }, [zoom]);

  useEffect(() => {
    if (layoutVersion > 0) canvasRef.current?.resetLayout();
  }, [layoutVersion]);

  useEffect(() => {
    if (!workspace || visible.nodes.length === 0) return;
    canvasRef.current?.applyWorkspace(workspace);
  }, [visible.nodes.length, workspace]);

  useEffect(() => {
    if (visible.nodes.length === 0 || viewMode === "network") return;
    const positions = viewMode === "hierarchy"
      ? hierarchyLayout(visible)
      : connectionsLayout(visible, selectedNodeId);
    canvasRef.current?.applyPositions(positions);
    canvasRef.current?.fitToView();
  }, [selectedNodeId, viewMode, visible]);

  if (visible.nodes.length === 0) {
    const emptyLabel = viewMode === "connections"
      ? "Select an entity to inspect its connections"
      : typeFilter === "all" ? "Graph ready" : "No entities match this filter";
    return <div className="empty-state"><Network size={34} /><span>{emptyLabel}</span></div>;
  }

  return (
    <IntelligenceCanvas
      ref={canvasRef}
      graph={visible}
      selectedNodeId={selectedNodeId}
      viewMode={viewMode}
      compact={compact}
      onWorkspaceChange={onWorkspaceChange}
      onSelectNode={(node) => propsRef.current.onSelectNode?.(node)}
      onNodeClick={(node, position) => propsRef.current.onNodeClick?.(node, position)}
      onNodeContextMenu={(node, position) => propsRef.current.onNodeContextMenu?.(node, position)}
    />
  );
});
