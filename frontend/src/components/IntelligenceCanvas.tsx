/**
 * IntelligenceCanvas — thin React wrapper around the GraphEngine.
 * Handles lifecycle: mount/unmount, data updates, and exposes CanvasHandle.
 */

import { useEffect, useImperativeHandle, useRef, forwardRef, useState } from "react";
import { GraphEngine } from "../graph";
import type { EngineWorkspaceState } from "../graph/types";
import type { GraphNode, GraphRead } from "../types";

export interface CanvasHandle {
  resetLayout: () => void;
  setZoom: (z: number) => void;
  getZoom: () => number;
  fitToView: () => void;
  focusNode: (nodeId: string) => void;
  getWorkspace: () => EngineWorkspaceState | null;
  applyWorkspace: (workspace: EngineWorkspaceState) => void;
  applyPositions: (positions: Record<string, { x: number; y: number }>) => void;
  togglePinned: (nodeId: string) => boolean;
  isPinned: (nodeId: string) => boolean;
  zoomBy: (factor: number) => void;
  undo: () => boolean;
  redo: () => boolean;
  getSelectedNodeIds: () => string[];
  selectAll: () => void;
  clearSelection: () => void;
  engine: GraphEngine | null;
}

interface Props {
  graph: GraphRead;
  selectedNodeId?: string;
  viewMode?: "network" | "hierarchy" | "connections";
  compact?: boolean;
  onSelectNode?: (node: GraphNode) => void;
  onNodeClick?: (node: GraphNode, screen: { x: number; y: number }) => void;
  onNodeContextMenu?: (node: GraphNode, screen: { x: number; y: number }) => void;
  onWorkspaceChange?: (workspace: EngineWorkspaceState) => void;
}

const IntelligenceCanvas = forwardRef<CanvasHandle, Props>(function IntelligenceCanvas(
  { graph, selectedNodeId, compact = false, onSelectNode, onNodeClick, onNodeContextMenu, onWorkspaceChange },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const engineRef = useRef<GraphEngine | null>(null);
  const [engineReady, setEngineReady] = useState(false);
  const [minimap, setMinimap] = useState<EngineWorkspaceState | null>(null);

  // Callback refs — stable across renders
  const onSelectNodeRef = useRef(onSelectNode);
  const onNodeClickRef = useRef(onNodeClick);
  const onNodeContextMenuRef = useRef(onNodeContextMenu);
  const onWorkspaceChangeRef = useRef(onWorkspaceChange);
  onSelectNodeRef.current = onSelectNode;
  onNodeClickRef.current = onNodeClick;
  onNodeContextMenuRef.current = onNodeContextMenu;
  onWorkspaceChangeRef.current = onWorkspaceChange;

  // Exposed methods
  useImperativeHandle(ref, () => ({
    resetLayout: () => engineRef.current?.resetLayout(),
    setZoom: (z: number) => {
      if (engineRef.current) {
        const cam = engineRef.current.store.camera;
        engineRef.current.store.updateCamera({ ...cam, zoom: Math.max(0.1, Math.min(4, z)) });
      }
    },
    getZoom: () => engineRef.current?.store.camera.zoom ?? 1,
    fitToView: () => engineRef.current?.fitToView(),
    focusNode: (nodeId: string) => engineRef.current?.focusNode(nodeId),
    getWorkspace: () => engineRef.current?.getWorkspace() ?? null,
    applyWorkspace: (workspace) => engineRef.current?.applyWorkspace(workspace, true),
    applyPositions: (positions) => engineRef.current?.applyPositions(positions),
    togglePinned: (nodeId) => engineRef.current?.togglePinned(nodeId) ?? false,
    isPinned: (nodeId) => engineRef.current?.isPinned(nodeId) ?? false,
    zoomBy: (factor) => engineRef.current?.zoomBy(factor),
    undo: () => engineRef.current?.undo() ?? false,
    redo: () => engineRef.current?.redo() ?? false,
    getSelectedNodeIds: () => Array.from(engineRef.current?.store.selectedNodeIds ?? []),
    selectAll: () => engineRef.current?.store.setSelectedMany(graph.nodes.map((node) => node.id)),
    clearSelection: () => engineRef.current?.store.setSelected(null),
    engine: engineRef.current,
  }));

  // Mount / unmount engine
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const engine = new GraphEngine();
    engineRef.current = engine;

    engine.mount(canvas, container, {
      onSelectNode: (node) => { if (node) onSelectNodeRef.current?.(node); },
      onNodeClick: (node, pos) => onNodeClickRef.current?.(node, pos),
      onNodeContextMenu: (node, pos) => onNodeContextMenuRef.current?.(node, pos),
    });
    const unsubscribe = engine.on((event) => {
      if (event.type === "workspace-change") onWorkspaceChangeRef.current?.(event.workspace);
    });

    setEngineReady(true);

    return () => {
      engine.unmount();
      unsubscribe();
      engineRef.current = null;
      setEngineReady(false);
    };
  }, []);

  useEffect(() => {
    if (!engineReady || compact) return;
    const update = () => setMinimap(engineRef.current?.getWorkspace() ?? null);
    update();
    const interval = window.setInterval(update, 500);
    return () => window.clearInterval(interval);
  }, [compact, engineReady]);

  // Update graph data
  useEffect(() => {
    if (!engineReady) return;
    engineRef.current?.setGraph(graph);
  }, [graph, engineReady]);

  // Update compact mode
  useEffect(() => {
    if (!engineReady) return;
    engineRef.current?.setCompact(compact);
  }, [compact, engineReady]);

  // Sync external selection changes to the engine
  useEffect(() => {
    if (!engineReady) return;
    const engine = engineRef.current;
    const next = selectedNodeId || null;
    if (engine && engine.store.selectedNodeId !== next) engine.store.setSelected(next);
  }, [selectedNodeId, engineReady]);

  if (graph.nodes.length === 0) {
    return (
      <div
        ref={containerRef}
        style={{
          width: "100%",
          height: "100%",
          minHeight: compact ? "300px" : "500px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span style={{ color: "#86a99f", fontSize: "14px" }}>Grafo preparado</span>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        height: "100%",
        minHeight: compact ? "300px" : "500px",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <canvas
        ref={canvasRef}
        tabIndex={0}
        aria-label="Interactive intelligence graph. Drag nodes, drag the background to pan, use Shift-click for multi-selection, F to fit, and Escape to clear selection."
        style={{
          display: "block",
          width: "100%",
          height: "100%",
          cursor: "default",
        }}
      />
      {!compact && minimap && Object.keys(minimap.positions).length > 0 && (() => {
        const positions = Object.entries(minimap.positions);
        const xs = positions.map(([, point]) => point.x);
        const ys = positions.map(([, point]) => point.y);
        const minX = Math.min(...xs) - 30;
        const minY = Math.min(...ys) - 30;
        const width = Math.max(60, Math.max(...xs) - Math.min(...xs) + 60);
        const height = Math.max(60, Math.max(...ys) - Math.min(...ys) + 60);
        return <button type="button" className="intelligence-minimap" title="Fit graph to screen" onClick={() => engineRef.current?.fitToView()}>
          <svg viewBox={`${minX} ${minY} ${width} ${height}`} role="img" aria-label="Graph minimap">
            {graph.edges.map((edge) => {
              const from = minimap.positions[edge.source];
              const to = minimap.positions[edge.target];
              return from && to ? <line key={edge.id} x1={from.x} y1={from.y} x2={to.x} y2={to.y} /> : null;
            })}
            {positions.map(([id, point]) => <circle key={id} cx={point.x} cy={point.y} r={point.pinned ? 8 : 6} className={id === selectedNodeId ? "selected" : point.pinned ? "pinned" : ""} />)}
          </svg>
        </button>;
      })()}
    </div>
  );
});

export default IntelligenceCanvas;
