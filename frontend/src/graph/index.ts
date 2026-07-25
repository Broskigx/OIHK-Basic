/**
 * GraphEngine — master controller that wires all graph subsystems together.
 * Manages the rAF loop, dirty flag checking, and subsystem coordination.
 */

import type { GraphRead, GraphNode, GraphEdge } from "../types";
import type { EngineWorkspaceState, GraphEngineEvent, GraphEventHandler } from "./types";
import { GraphStore } from "./store";
import { GraphLayoutEngine } from "./layout";
import { renderGraph, type RenderScene } from "./renderer";
import { GraphSpatialIndex } from "./spatial";
import { GraphInteractionController } from "./interaction";
import { fitToView } from "./camera";

export interface EngineCallbacks {
  onSelectNode?: (node: GraphNode | null) => void;
  onNodeClick?: (node: GraphNode, screen: { x: number; y: number }) => void;
  onNodeContextMenu?: (node: GraphNode, screen: { x: number; y: number }) => void;
}

export class GraphEngine {
  readonly store: GraphStore;
  readonly layout: GraphLayoutEngine;
  readonly spatial: GraphSpatialIndex;
  interaction: GraphInteractionController | null = null;

  private renderer = { render: renderGraph };
  private canvas: HTMLCanvasElement | null = null;
  private container: HTMLElement | null = null;
  private animFrameId = 0;
  private running = false;
  private rawNodes: GraphNode[] = [];
  private rawEdges: GraphEdge[] = [];
  private compact = false;
  private callbacks: EngineCallbacks = {};
  private eventHandlers: Set<GraphEventHandler> = new Set();
  private history: EngineWorkspaceState[] = [];
  private historyIndex = -1;

  private _findGraphNode(id: string): GraphNode | undefined {
    return this.rawNodes.find((n) => n.id === id);
  }

  constructor() {
    this.store = new GraphStore();
    this.layout = new GraphLayoutEngine();
    this.spatial = new GraphSpatialIndex();
  }

  // ── Mount / unmount ──

  mount(canvas: HTMLCanvasElement, container: HTMLElement, callbacks?: EngineCallbacks): void {
    this.canvas = canvas;
    this.container = container;
    this.callbacks = callbacks ?? {};
    this.running = true;

    this.interaction = new GraphInteractionController(this.store, this.spatial, this.layout, {
      onSelect: (nodeId, additive) => {
        this.store.setSelected(nodeId, additive);
        const node = nodeId ? this._findGraphNode(nodeId) : null;
        this.callbacks.onSelectNode?.(node ?? null);
        this._emit({ type: "select", nodeId });
      },
      onHover: (nodeId) => {
        this.store.setHovered(nodeId);
        this._emit({ type: "hover", nodeId });
      },
      onClick: (nodeId, screenX, screenY) => {
        const node = this._findGraphNode(nodeId);
        if (node) {
          this.callbacks.onNodeClick?.(node, { x: screenX, y: screenY });
          this._emit({ type: "click", nodeId, screenX, screenY });
        }
      },
      onContext: (nodeId, screenX, screenY) => {
        const node = this._findGraphNode(nodeId);
        if (node) {
          this.callbacks.onNodeContextMenu?.(node, { x: screenX, y: screenY });
          this._emit({ type: "context", nodeId, screenX, screenY });
        }
      },
      onDragEnd: (nodeId, x, y) => {
        this._emit({ type: "drag-end", nodeId, x, y });
      },
      onViewportChange: (camera) => this._emit({ type: "viewport-change", camera }),
      onCommit: () => this.commitWorkspace(),
    });

    this.interaction.attach(canvas);
    this._resize();
    this._tick();
  }

  unmount(): void {
    this.running = false;
    cancelAnimationFrame(this.animFrameId);
    this.interaction?.detach();
    this.interaction = null;
    this.layout.stop();
    this.canvas = null;
    this.container = null;
  }

  // ── Data updates ──

  setGraph(graph: GraphRead): void {
    this.rawNodes = graph.nodes;
    this.rawEdges = graph.edges;
    this.layout.init(graph, this.layout.nodes);
    this.layout.start();
    this.spatial.rebuild(this.layout.nodes.map((n) => ({ id: n.id, x: n.x, y: n.y, radius: n.radius })));
    this.store.setGraphData(this.layout.nodes, graph.edges);
    if (this.history.length === 0) this.commitWorkspace();
  }

  setCompact(value: boolean): void {
    if (this.compact === value) return;
    this.compact = value;
    this.store.markDirty("data");
  }

  setCallbacks(callbacks: EngineCallbacks): void {
    this.callbacks = callbacks;
  }

  // ── Camera actions ──

  fitToView(): void {
    if (!this.canvas) return;
    const { width, height } = this.canvas.getBoundingClientRect();
    const points = this.layout.nodes.map((n) => ({ x: n.x, y: n.y }));
    this.store.updateCamera(fitToView(points, width, height));
    this.commitWorkspace();
  }

  focusNode(nodeId: string): void {
    const node = this.layout.nodes.find((n) => n.id === nodeId);
    if (!node || !this.canvas) return;
    this.store.updateCamera({
      x: -node.x,
      y: -node.y,
      zoom: Math.max(0.8, this.store.camera.zoom),
    });
    this.store.setSelected(nodeId);
    this.commitWorkspace();
  }

  resetLayout(): void {
    this.layout.init(
      { nodes: this.rawNodes, edges: this.rawEdges },
      undefined,
    );
    this.layout.start();
    this.spatial.rebuild(this.layout.nodes.map((n) => ({ id: n.id, x: n.x, y: n.y, radius: n.radius })));
    this.store.setGraphData(this.layout.nodes, this.rawEdges);
    this.store.markDirty("layout");
    this.commitWorkspace();
  }

  getWorkspace(): EngineWorkspaceState {
    return {
      positions: Object.fromEntries(
        this.layout.nodes.map((node) => [node.id, { x: node.x, y: node.y, pinned: node.pinned }]),
      ),
      camera: { ...this.store.camera },
    };
  }

  applyWorkspace(workspace: EngineWorkspaceState, record = false): void {
    for (const node of this.layout.nodes) {
      const position = workspace.positions[node.id];
      if (!position) continue;
      node.x = position.x;
      node.y = position.y;
      node.vx = 0;
      node.vy = 0;
      node.pinned = position.pinned;
    }
    this.layout.stop();
    this.store.updateCamera({ ...workspace.camera });
    this.spatial.rebuild(this.layout.nodes.map((node) => ({ id: node.id, x: node.x, y: node.y, radius: node.radius })));
    this.store.setGraphData(this.layout.nodes, this.rawEdges);
    this.store.markDirty("layout");
    if (record) this.commitWorkspace();
  }

  applyPositions(positions: Record<string, { x: number; y: number }>): void {
    this.layout.applyPositions(positions);
    this.spatial.rebuild(this.layout.nodes.map((node) => ({ id: node.id, x: node.x, y: node.y, radius: node.radius })));
    this.store.markDirty("layout");
    this.commitWorkspace();
  }

  togglePinned(nodeId: string): boolean {
    const node = this.layout.nodes.find((item) => item.id === nodeId);
    if (!node) return false;
    node.pinned = !node.pinned;
    this.store.markDirty("interaction");
    this.commitWorkspace();
    return node.pinned;
  }

  isPinned(nodeId: string): boolean {
    return this.layout.nodes.find((item) => item.id === nodeId)?.pinned ?? false;
  }

  zoomBy(factor: number): void {
    const camera = this.store.camera;
    this.store.updateCamera({ ...camera, zoom: Math.max(0.1, Math.min(4, camera.zoom * factor)) });
    this.commitWorkspace();
  }

  commitWorkspace(): void {
    const workspace = this.getWorkspace();
    const serialized = JSON.stringify(workspace);
    const current = this.history[this.historyIndex];
    if (current && JSON.stringify(current) === serialized) return;
    this.history = this.history.slice(0, this.historyIndex + 1);
    this.history.push(JSON.parse(serialized) as EngineWorkspaceState);
    if (this.history.length > 60) this.history.shift();
    this.historyIndex = this.history.length - 1;
    this._emit({ type: "workspace-change", workspace });
  }

  undo(): boolean {
    if (this.historyIndex <= 0) return false;
    this.historyIndex -= 1;
    this.applyWorkspace(this.history[this.historyIndex]);
    this._emit({ type: "workspace-change", workspace: this.getWorkspace() });
    return true;
  }

  redo(): boolean {
    if (this.historyIndex >= this.history.length - 1) return false;
    this.historyIndex += 1;
    this.applyWorkspace(this.history[this.historyIndex]);
    this._emit({ type: "workspace-change", workspace: this.getWorkspace() });
    return true;
  }

  // ── Events ──

  on(handler: GraphEventHandler): () => void {
    this.eventHandlers.add(handler);
    return () => this.eventHandlers.delete(handler);
  }

  private _emit(event: GraphEngineEvent): void {
    for (const handler of this.eventHandlers) {
      handler(event);
    }
  }

  // ── Internal ──

  private _resize(): void {
    const canvas = this.canvas;
    const container = this.container;
    if (!canvas || !container) return;
    const dpr = window.devicePixelRatio || 1;
    const w = container.clientWidth;
    const h = container.clientHeight;
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
    }
  }

  private _tick = (): void => {
    if (!this.running) return;

    const canvas = this.canvas;
    const container = this.container;
    if (!canvas || !container) return;

    // Resize handling
    this._resize();
    const dpr = window.devicePixelRatio || 1;
    const w = container.clientWidth;
    const h = container.clientHeight;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Count layout nodes
    if (this.layout.nodes.length !== this.rawNodes.length) {
      this.layout.init({ nodes: this.rawNodes, edges: this.rawEdges }, this.layout.nodes);
      this.layout.start();
    }

    // Run layout step if active
    const layoutActive = this.layout.tick({ nodes: this.rawNodes, edges: this.rawEdges });
    if (layoutActive || this.layout.nodes.length !== this.rawNodes.length) {
      this.spatial.rebuild(this.layout.nodes.map((n) => ({ id: n.id, x: n.x, y: n.y, radius: n.radius })));
      this.store.markDirty("layout");
    }
    if (!layoutActive && this.layout.converged && !this.store.isDirty) {
      // Everything is still: skip render to save CPU
      this.animFrameId = requestAnimationFrame(this._tick);
      return;
    }

    // Check if there's anything to update
    const dirty = this.store.dirty;
    if (!layoutActive && !Object.values(dirty).some(Boolean)) {
      this.animFrameId = requestAnimationFrame(this._tick);
      return;
    }

    // Build scene & render
    ctx.save();
    ctx.scale(dpr, dpr);

    const scene: RenderScene = {
      nodes: this.layout.nodes,
      edges: this.store.edges,
      camera: this.store.camera,
      selectedId: this.store.selectedNodeId,
      selectedIds: this.store.selectedNodeIds,
      hoveredId: this.store.hoveredNodeId,
      compact: this.compact,
      cameraZoom: this.store.camera.zoom,
    };

    this.renderer.render(ctx, scene, w, h, dirty);

    ctx.restore();

    // Consume dirty flags after render
    this.store.consumeDirty();
    this.store.dirty.layout = layoutActive;

    this.animFrameId = requestAnimationFrame(this._tick);
  };
}
