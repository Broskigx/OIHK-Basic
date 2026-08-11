/**
 * GraphStore — centralized state for the graph engine.
 * Holds data (nodes/edges), UI state (selection, hover), camera, and dirty flags.
 */

import type { CameraState, DirtyFlags, LayoutNode } from "./types";
import { createCamera } from "./camera";

export class GraphStore {
  // ── Raw graph data ──
  nodeLabels = new Map<string, string>();   // nodeId → label
  edges: Array<{ source: string; target: string; label: string }> = [];

  // ── UI state ──
  selectedNodeId: string | null = null;
  selectedNodeIds = new Set<string>();
  hoveredNodeId: string | null = null;

  // ── Camera ──
  private _camera: CameraState = createCamera();

  get camera(): CameraState {
    return this._camera;
  }

  // ── Dirty flags ──
  dirty: DirtyFlags = {
    camera: true,
    data: true,
    layout: true,
    interaction: true,
    minimap: true,
  };

  // ── State ──
  get state() {
    return {
      camera: this._camera,
      selectedId: this.selectedNodeId,
      hoveredId: this.hoveredNodeId,
    };
  }

  // ── Camera mutations ──
  updateCamera(camera: CameraState): void {
    this._camera = camera;
    this.dirty.camera = true;
    this.dirty.minimap = true;
  }

  // ── Data mutations ──
  setGraphData(
    nodes: LayoutNode[],
    edges: Array<{ source: string; target: string; label: string }>,
  ): void {
    this.nodeLabels.clear();
    for (const node of nodes) {
      this.nodeLabels.set(node.id, node.label);
    }
    // Sort edges for deterministic rendering
    this.edges = edges.sort((a, b) => a.label.localeCompare(b.label));
    this.dirty.data = true;
    this.dirty.layout = true;
  }

  // ── Selection ──
  setSelected(nodeId: string | null, additive = false): void {
    if (!additive) this.selectedNodeIds.clear();
    if (nodeId && additive && this.selectedNodeIds.has(nodeId)) {
      this.selectedNodeIds.delete(nodeId);
      this.selectedNodeId = this.selectedNodeIds.values().next().value ?? null;
    } else if (nodeId) {
      this.selectedNodeIds.add(nodeId);
      this.selectedNodeId = nodeId;
    } else if (!additive) {
      this.selectedNodeId = null;
    }
    this.dirty.interaction = true;
  }

  setSelectedMany(nodeIds: Iterable<string>): void {
    this.selectedNodeIds = new Set(nodeIds);
    this.selectedNodeId = this.selectedNodeIds.values().next().value ?? null;
    this.dirty.interaction = true;
  }

  setHovered(nodeId: string | null): void {
    if (this.hoveredNodeId === nodeId) return;
    this.hoveredNodeId = nodeId;
    this.dirty.interaction = true;
  }

  // ── Dirty flag helpers ──
  markDirty(flag: keyof DirtyFlags): void {
    this.dirty[flag] = true;
  }

  /**
   * Returns true if any flag is dirty. Resets all flags when called.
   * Call once per frame after rendering.
   */
  consumeDirty(): boolean {
    const any = Object.values(this.dirty).some(Boolean);
    if (any) {
      this.dirty = { camera: false, data: false, layout: false, interaction: false, minimap: false };
    }
    return any;
  }

  /** Whether any dirty flag is set (without consuming) */
  get isDirty(): boolean {
    return Object.values(this.dirty).some(Boolean);
  }
}
