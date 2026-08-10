/**
 * GraphInteractionController — handles mouse and keyboard events.
 * Delegates to camera, store, and layout. No React dependencies.
 */

import { type CameraState } from "./types";
import { screenToWorld, panCamera, zoomCamera } from "./camera";
import type { GraphStore } from "./store";
import type { GraphSpatialIndex } from "./spatial";
import type { GraphLayoutEngine } from "./layout";

export interface InteractionCallbacks {
  onSelect: (nodeId: string | null, additive: boolean) => void;
  onHover: (nodeId: string | null) => void;
  onClick: (nodeId: string, screenX: number, screenY: number) => void;
  onContext: (nodeId: string, screenX: number, screenY: number) => void;
  onDragEnd: (nodeId: string, x: number, y: number) => void;
  onViewportChange: (camera: CameraState) => void;
  onCommit: () => void;
}

export class GraphInteractionController {
  private canvas: HTMLCanvasElement | null = null;
  private store: GraphStore;
  private spatial: GraphSpatialIndex;
  private layout: GraphLayoutEngine;

  private callbacks: InteractionCallbacks;
  private dragNodeId: string | null = null;
  private panning = false;
  private dragStart = { x: 0, y: 0 };
  private cameraStart = { x: 0, y: 0 };
  private wasDragged = false;
  private wheelCommitTimer: number | null = null;
  /** Cached canvas rect captured at gesture start; avoids forcing a sync
   *  layout reflow via getBoundingClientRect() on every mousemove. */
  private rectCache: DOMRect | null = null;

  private boundHandlers: {
    onDown: (e: MouseEvent) => void;
    onMove: (e: MouseEvent) => void;
    onUp: (e: MouseEvent) => void;
    onWheel: (e: WheelEvent) => void;
    onContext: (e: MouseEvent) => void;
    onLeave: () => void;
  } | null = null;

  constructor(
    store: GraphStore,
    spatial: GraphSpatialIndex,
    layout: GraphLayoutEngine,
    callbacks: InteractionCallbacks,
  ) {
    this.store = store;
    this.spatial = spatial;
    this.layout = layout;
    this.callbacks = callbacks;
  }

  attach(canvas: HTMLCanvasElement): void {
    this.canvas = canvas;

    const onDown = (e: MouseEvent) => this._onPointerDown(e);
    const onMove = (e: MouseEvent) => this._onPointerMove(e);
    const onUp = (e: MouseEvent) => this._onPointerUp(e);
    const onWheel = (e: WheelEvent) => this._onWheel(e);
    const onContext = (e: MouseEvent) => this._onContextMenu(e);
    const onLeave = () => this._onPointerLeave();

    canvas.addEventListener("mousedown", onDown);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("contextmenu", onContext);
    canvas.addEventListener("mouseleave", onLeave);

    this.boundHandlers = { onDown, onMove, onUp, onWheel, onContext, onLeave };
  }

  detach(): void {
    if (!this.canvas || !this.boundHandlers) return;
    const { onDown, onMove, onUp, onWheel, onContext, onLeave } = this.boundHandlers;
    this.canvas.removeEventListener("mousedown", onDown);
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseup", onUp);
    this.canvas.removeEventListener("wheel", onWheel);
    this.canvas.removeEventListener("contextmenu", onContext);
    this.canvas.removeEventListener("mouseleave", onLeave);
    this.boundHandlers = null;
    if (this.wheelCommitTimer !== null) window.clearTimeout(this.wheelCommitTimer);
    this.wheelCommitTimer = null;
    this.rectCache = null;
    this.canvas = null;
  }

  // ── Private handlers ──

  private _canvasWH(): { w: number; h: number } {
    if (!this.canvas) return { w: 800, h: 600 };
    return { w: this.canvas.width / (window.devicePixelRatio || 1), h: this.canvas.height / (window.devicePixelRatio || 1) };
  }

  /** Canvas rect relative to the viewport. Uses the gesture-cached rect when
   *  available and only falls back to getBoundingClientRect() outside a gesture. */
  private _canvasRect(): DOMRect {
    if (this.rectCache) return this.rectCache;
    return this.canvas!.getBoundingClientRect();
  }

  private _camera(): CameraState {
    return this.store.state.camera;
  }

  private _hitTest(screenX: number, screenY: number) {
    if (!this.canvas) return null;
    const rect = this._canvasRect();
    const { w, h } = this._canvasWH();
    const world = screenToWorld(screenX - rect.left, screenY - rect.top, this._camera(), w, h);
    const hit = this.spatial.hitTest(world.x, world.y, 12);
    return hit;
  }

  private _onPointerDown(e: MouseEvent): void {
    const canvas = this.canvas;
    if (!canvas) return;
    canvas.focus({ preventScroll: true });
    // Cache the canvas rect once per gesture; reused for every move/up event
    this.rectCache = canvas.getBoundingClientRect();
    const rect = this.rectCache;
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;

    if (e.button === 1) {
      // Middle-click pan
      this.panning = true;
      this.dragStart = { x: sx, y: sy };
      this.cameraStart = { x: this._camera().x, y: this._camera().y };
      canvas.style.cursor = "grabbing";
      return;
    }
    if (e.button !== 0) return;

    this.dragStart = { x: sx, y: sy };
    this.wasDragged = false;

    const hit = this._hitTest(e.clientX, e.clientY);
    if (hit) {
      this.dragNodeId = hit.id;
      this.layout.setPinned(hit.id, true);
      canvas.style.cursor = "grabbing";
      this.callbacks.onSelect(hit.id, e.shiftKey || e.ctrlKey || e.metaKey);
    } else {
      this.panning = true;
      this.cameraStart = { x: this._camera().x, y: this._camera().y };
      canvas.style.cursor = "grabbing";
      this.callbacks.onSelect(null, false);
    }
  }

  private _onPointerMove(e: MouseEvent): void {
    const canvas = this.canvas;
    if (!canvas) return;

    if (this.panning) {
      const dx = (e.movementX) / this._camera().zoom;
      const dy = (e.movementY) / this._camera().zoom;
      const camera = panCamera(this._camera(), dx, dy);
      this.store.updateCamera(camera);
      this.callbacks.onViewportChange(camera);
      this.wasDragged = true;
      return;
    }

    if (this.dragNodeId) {
      const node = this.layout.nodes.find((n) => n.id === this.dragNodeId);
      if (node) {
        const dx = (e.movementX) / this._camera().zoom;
        const dy = (e.movementY) / this._camera().zoom;
        node.x += dx;
        node.y += dy;
        this.spatial.upsert({ id: node.id, x: node.x, y: node.y, radius: node.radius });
        this.store.markDirty("layout");
        this.wasDragged = true;
      }
      // While dragging we already know what is under the cursor — skip the
      // redundant hit-test and hover updates until the gesture ends.
      return;
    }

    // Hover
    const hit = this._hitTest(e.clientX, e.clientY);
    const hoverId = hit?.id ?? null;
    this.store.setHovered(hoverId);
    canvas.style.cursor = hoverId ? "pointer" : "default";
  }

  private _onPointerUp(e: MouseEvent): void {
    const canvas = this.canvas;
    this.rectCache = null; // gesture over — drop the cached rect
    if (e.button === 1 || this.panning) {
      this.panning = false;
      if (canvas) canvas.style.cursor = "default";
      this.dragNodeId = null;
      if (this.wasDragged) this.callbacks.onCommit();
      return;
    }

    if (this.dragNodeId) {
      const node = this.layout.nodes.find((n) => n.id === this.dragNodeId);
      if (node) {
        this.spatial.upsert({ id: node.id, x: node.x, y: node.y, radius: node.radius });
      }
      if (!this.wasDragged) {
        // Click (not drag)
        this.callbacks.onClick(this.dragNodeId, e.clientX, e.clientY);
      } else {
        this.callbacks.onDragEnd(this.dragNodeId, node?.x ?? 0, node?.y ?? 0);
        this.callbacks.onCommit();
      }
      this.dragNodeId = null;
      if (canvas) canvas.style.cursor = "default";
    }
    this.panning = false;
  }

  private _onWheel(e: WheelEvent): void {
    e.preventDefault();
    if (!this.canvas) return;
    const rect = this._canvasRect();
    const factor = e.deltaY > 0 ? 0.88 : 1.12;
    const { w, h } = this._canvasWH();
    const newCamera = zoomCamera(
      this._camera(),
      factor,
      e.clientX - rect.left,
      e.clientY - rect.top,
      w,
      h,
    );
    this.store.updateCamera(newCamera);
    this.callbacks.onViewportChange(newCamera);
    if (this.wheelCommitTimer !== null) window.clearTimeout(this.wheelCommitTimer);
    this.wheelCommitTimer = window.setTimeout(() => {
      this.callbacks.onCommit();
      this.wheelCommitTimer = null;
    }, 180);
  }

  private _onContextMenu(e: MouseEvent): void {
    e.preventDefault();
    const hit = this._hitTest(e.clientX, e.clientY);
    if (hit) {
      this.callbacks.onSelect(hit.id, false);
      this.callbacks.onContext(hit.id, e.clientX, e.clientY);
    }
  }

  private _onPointerLeave(): void {
    this.rectCache = null;
    if (this.dragNodeId) {
      this.dragNodeId = null;
    }
    this.panning = false;
    this.store.setHovered(null);
    if (this.canvas) this.canvas.style.cursor = "default";
  }
}
