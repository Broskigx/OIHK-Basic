/** Graph engine types — internal data structures for the custom Canvas engine */

export interface CameraState {
  x: number;
  y: number;
  zoom: number;
}

export interface EngineWorkspaceState {
  positions: Record<string, { x: number; y: number; pinned: boolean }>;
  camera: CameraState;
}

export const MIN_ZOOM = 0.1;
export const MAX_ZOOM = 4;

export interface LayoutNode {
  id: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  type: string;
  label: string;
  category: string;
  confidence: number;
  pinned: boolean;
  /** @internal layout iteration counter — reset when position changes externally */
  _iter: number;
}

export interface DirtyFlags {
  camera: boolean;
  data: boolean;
  layout: boolean;
  interaction: boolean;
  minimap: boolean;
}

export interface GraphScene {
  nodes: LayoutNode[];
  edgeCount: number;
  camera: CameraState;
  selectedId: string | null;
  hoveredId: string | null;
}

export interface ViewportBounds {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface HitResult {
  type: "node" | "edge" | "background";
  id?: string;
  distance?: number;
}

export interface SpatialItem {
  id: string;
  x: number;
  y: number;
  radius: number;
}

export type GraphEngineEvent =
  | { type: "select"; nodeId: string | null }
  | { type: "hover"; nodeId: string | null }
  | { type: "click"; nodeId: string; screenX: number; screenY: number }
  | { type: "context"; nodeId: string; screenX: number; screenY: number }
  | { type: "drag-end"; nodeId: string; x: number; y: number }
  | { type: "viewport-change"; camera: CameraState }
  | { type: "workspace-change"; workspace: EngineWorkspaceState }
  | { type: "layout-converged" };

export type GraphEventHandler = (event: GraphEngineEvent) => void;
