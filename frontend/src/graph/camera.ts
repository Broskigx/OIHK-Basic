/**
 * GraphCamera — pure camera/viewport transforms for the intelligence graph.
 * No React dependencies. All functions are stateless; pass/return CameraState.
 */

import { MIN_ZOOM, MAX_ZOOM, type CameraState } from "./types";

/** Create default camera centered at origin with zoom=1 */
export function createCamera(): CameraState {
  return { x: 0, y: 0, zoom: 1 };
}

/** Convert screen pixel coordinates → world coordinates */
export function screenToWorld(
  sx: number,
  sy: number,
  camera: CameraState,
  canvasW: number,
  canvasH: number,
): { x: number; y: number } {
  return {
    x: (sx - canvasW / 2) / camera.zoom - camera.x,
    y: (sy - canvasH / 2) / camera.zoom - camera.y,
  };
}

/** Pan the camera by a delta in WORLD space */
export function panCamera(camera: CameraState, dx: number, dy: number): CameraState {
  return { ...camera, x: camera.x + dx, y: camera.y + dy };
}

/** Zoom camera centered on a screen point (e.g., cursor position) */
export function zoomCamera(
  camera: CameraState,
  factor: number,
  screenX: number,
  screenY: number,
  canvasW: number,
  canvasH: number,
): CameraState {
  const world = screenToWorld(screenX, screenY, camera, canvasW, canvasH);
  const newZoom = clamp(camera.zoom * factor, MIN_ZOOM, MAX_ZOOM);
  return {
    x: world.x - (screenX - canvasW / 2) / newZoom,
    y: world.y - (screenY - canvasH / 2) / newZoom,
    zoom: newZoom,
  };
}

/** Fit all given world points into the viewport */
export function fitToView(
  points: { x: number; y: number }[],
  canvasW: number,
  canvasH: number,
  padding = 0.9,
): CameraState {
  if (points.length === 0) return createCamera();
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const p of points) {
    if (p.x < minX) minX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.x > maxX) maxX = p.x;
    if (p.y > maxY) maxY = p.y;
  }
  const rangeX = maxX - minX || 1;
  const rangeY = maxY - minY || 1;
  const zoomX = (canvasW * padding) / (rangeX + 40);
  const zoomY = (canvasH * padding) / (rangeY + 40);
  const zoom = clamp(Math.min(zoomX, zoomY), MIN_ZOOM, MAX_ZOOM);
  return {
    x: -(minX + maxX) / 2,
    y: -(minY + maxY) / 2,
    zoom,
  };
}

/** Get visible world bounds from camera + canvas size */
export function getViewportBounds(
  camera: CameraState,
  canvasW: number,
  canvasH: number,
): { x1: number; y1: number; x2: number; y2: number } {
  const topLeft = screenToWorld(0, 0, camera, canvasW, canvasH);
  const bottomRight = screenToWorld(canvasW, canvasH, camera, canvasW, canvasH);
  return { x1: topLeft.x, y1: topLeft.y, x2: bottomRight.x, y2: bottomRight.y };
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
