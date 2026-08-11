/**
 * GraphRenderer — pure rendering pipeline for the intelligence graph Canvas.
 * Draws in layers: background → grid → grouping regions → edges → nodes → labels → overlays.
 * No React. Receives data and draws; returns void.
 */

import type { CameraState, LayoutNode, DirtyFlags } from "./types";
import { getViewportBounds } from "./camera";
import type { GraphSpatialIndex } from "./spatial";
import { getNodeConfig, CATEGORY_ORDER, CATEGORY_COLORS, CATEGORY_LABELS } from "../components/graphTypes";

// ── Shape drawing ──

function drawShape(
  ctx: CanvasRenderingContext2D,
  shape: string,
  x: number,
  y: number,
  radius: number,
): void {
  ctx.beginPath();
  switch (shape) {
    case "circle":
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      break;
    case "square":
      ctx.rect(x - radius * 0.8, y - radius * 0.8, radius * 1.6, radius * 1.6);
      break;
    case "diamond":
      ctx.moveTo(x, y - radius);
      ctx.lineTo(x + radius * 0.8, y);
      ctx.lineTo(x, y + radius);
      ctx.lineTo(x - radius * 0.8, y);
      ctx.closePath();
      break;
    case "hexagon":
      for (let i = 0; i < 6; i++) {
        const angle = (Math.PI / 3) * i - Math.PI / 6;
        const px = x + radius * Math.cos(angle);
        const py = y + radius * Math.sin(angle);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      break;
    case "triangle":
      ctx.moveTo(x, y - radius);
      ctx.lineTo(x + radius, y + radius * 0.7);
      ctx.lineTo(x - radius, y + radius * 0.7);
      ctx.closePath();
      break;
    default:
      ctx.arc(x, y, radius, 0, Math.PI * 2);
  }
}

// ── Edge drawing ──

function drawEdge(
  ctx: CanvasRenderingContext2D,
  from: LayoutNode,
  to: LayoutNode,
  label: string,
  highlighted: boolean,
  dimmed: boolean,
): void {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const dist = Math.sqrt(dx * dx + dy * dy);
  if (dist < 0.1) return;

  const nx = dx / dist;
  const ny = dy / dist;
  const sx = from.x + nx * from.radius;
  const sy = from.y + ny * from.radius;
  const ex = to.x - nx * to.radius;
  const ey = to.y - ny * to.radius;

  ctx.beginPath();
  ctx.moveTo(sx, sy);
  ctx.lineTo(ex, ey);
  if (highlighted) {
    ctx.strokeStyle = "rgba(102, 211, 71, 0.82)";
    ctx.lineWidth = 2.2;
  } else if (dimmed) {
    ctx.strokeStyle = "rgba(100, 116, 139, 0.15)";
    ctx.lineWidth = 0.8;
  } else {
    ctx.strokeStyle = "rgba(153, 166, 174, 0.3)";
    ctx.lineWidth = 1.2;
  }
  ctx.stroke();

  // Arrow head
  if (dist > from.radius + to.radius + 4) {
    const arrowSize = highlighted ? 8 : 6;
    ctx.beginPath();
    ctx.moveTo(ex, ey);
    ctx.lineTo(ex - nx * arrowSize - ny * arrowSize * 0.5, ey - ny * arrowSize + nx * arrowSize * 0.5);
    ctx.lineTo(ex - nx * arrowSize + ny * arrowSize * 0.5, ey - ny * arrowSize - nx * arrowSize * 0.5);
    ctx.closePath();
    ctx.fillStyle = highlighted
      ? "rgba(102, 211, 71, 0.9)"
      : dimmed
        ? "rgba(100, 116, 139, 0.2)"
        : "rgba(153, 166, 174, 0.42)";
    ctx.fill();
  }

  // Edge label
  if (label && !dimmed) {
    const midX = (sx + ex) / 2 + ny * 10;
    const midY = (sy + ey) / 2 - nx * 10;
    ctx.save();
    ctx.translate(midX, midY);
    ctx.rotate(Math.atan2(ny, nx));
    ctx.font = "9px Inter, system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillStyle = "rgba(148, 163, 184, 0.8)";
    ctx.fillText(label, 0, -2);
    ctx.restore();
  }
}

// ── Node label drawing ──

function drawLabel(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  zoom: number,
): void {
  if (zoom < 0.35) return;
  const fontSize = Math.max(9, Math.min(13, 11 * zoom));
  ctx.font = `600 ${fontSize}px Inter, system-ui, sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  const labelY = y + 14;

  const metrics = ctx.measureText(text);
  const pad = 4;
  const bw = metrics.width + pad * 2;
  const bh = fontSize + 4;
  ctx.fillStyle = "rgba(9, 13, 16, 0.88)";
  ctx.beginPath();
  ctx.roundRect(x - bw / 2, labelY - 1, bw, bh, 4);
  ctx.fill();

  ctx.fillStyle = "#edf1ee";
  ctx.fillText(text, x, labelY);
}

// ── Level of detail thresholds ──
const LOD_LABEL_THRESHOLD = 800; // hide labels below this zoom for large graphs
const LOD_NO_SHADOW_THRESHOLD = 3000; // skip expensive shadows/glow for huge graphs
const LOD_MIN_LABEL_ZOOM = 0.5;

// ── Main render function ──

export interface RenderScene {
  nodes: LayoutNode[];
  edges: Array<{ source: string; target: string; label: string }>;
  camera: CameraState;
  selectedId: string | null;
  selectedIds?: Set<string>;
  hoveredId: string | null;
  compact: boolean;
  cameraZoom: number;
  dimThreshold?: number; // LOD: hide labels below this zoom
  spatial?: GraphSpatialIndex; // optional spatial index used for viewport culling
}

/**
 * Full render pipeline. Draws into the provided 2D context.
 * Assumes ctx has been scaled for devicePixelRatio already.
 */
export function renderGraph(
  ctx: CanvasRenderingContext2D,
  scene: RenderScene,
  width: number,
  height: number,
  dirty: DirtyFlags,
): void {
  void dirty;
  const { nodes, edges, camera, selectedId, selectedIds = new Set(selectedId ? [selectedId] : []), hoveredId, compact, cameraZoom } = scene;
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  // Level of detail: degrade labels and shadows for very large graphs so the
  // main thread stays responsive while panning and zooming.
  const hideLabels = !compact && nodes.length > LOD_LABEL_THRESHOLD && cameraZoom < LOD_MIN_LABEL_ZOOM;
  const skipShadows = nodes.length > LOD_NO_SHADOW_THRESHOLD;

  // Viewport culling: only draw nodes/edges inside the visible world bounds
  // plus a ~60px screen margin (scaled to world units) so nothing pops in/out
  // at the edge while panning. Edges render when at least one endpoint is visible.
  const margin = 60 / cameraZoom;
  const viewportBounds = getViewportBounds(camera, width, height);
  const expandedBounds = {
    x1: viewportBounds.x1 - margin,
    y1: viewportBounds.y1 - margin,
    x2: viewportBounds.x2 + margin,
    y2: viewportBounds.y2 + margin,
  };
  let visibleNodes: LayoutNode[];
  if (scene.spatial) {
    const visibleIds = new Set(scene.spatial.queryViewport(expandedBounds).map((item) => item.id));
    visibleNodes = nodes.filter((n) => visibleIds.has(n.id));
  } else {
    visibleNodes = nodes.filter(
      (n) =>
        n.x + n.radius >= expandedBounds.x1 &&
        n.x - n.radius <= expandedBounds.x2 &&
        n.y + n.radius >= expandedBounds.y1 &&
        n.y - n.radius <= expandedBounds.y2,
    );
  }
  const visibleNodeIds = new Set(visibleNodes.map((n) => n.id));

  // 1. Background
  ctx.fillStyle = compact ? "transparent" : "#0a0f12";
  ctx.fillRect(0, 0, width, height);

  // 2. Grid (only in non-compact mode)
  if (!compact) {
    ctx.fillStyle = "rgba(153, 166, 174, 0.09)";
    const gridSize = 28;
    for (let x = gridSize / 2; x < width; x += gridSize) {
      for (let y = gridSize / 2; y < height; y += gridSize) {
        ctx.fillRect(x, y, 1, 1);
      }
    }
  }

  // 3. Camera transform
  ctx.save();
  ctx.translate(width / 2, height / 2);
  ctx.scale(cameraZoom, cameraZoom);
  ctx.translate(camera.x, camera.y);

  // Pre-compute selection neighborhood
  const selectedNeighborhood = new Set<string>();
  if (selectedIds.size) {
    selectedIds.forEach((id) => selectedNeighborhood.add(id));
    for (const edge of edges) {
      if (selectedIds.has(edge.source)) selectedNeighborhood.add(edge.target);
      if (selectedIds.has(edge.target)) selectedNeighborhood.add(edge.source);
    }
  }

  const hoverNeighbor = hoveredId && !selectedId;
  if (hoverNeighbor) {
    selectedNeighborhood.add(hoveredId);
    for (const edge of edges) {
      if (edge.source === hoveredId) selectedNeighborhood.add(edge.target);
      if (edge.target === hoveredId) selectedNeighborhood.add(edge.source);
    }
  }

  // 4. Draw edges
  for (const edge of edges) {
    const from = nodeMap.get(edge.source);
    const to = nodeMap.get(edge.target);
    if (!from || !to) continue;
    // Cull: draw an edge only when at least one endpoint is inside the viewport
    if (!visibleNodeIds.has(edge.source) && !visibleNodeIds.has(edge.target)) continue;

    const activeId = selectedIds.size ? null : hoveredId;
    const highlighted = selectedIds.size
      ? selectedIds.has(edge.source) || selectedIds.has(edge.target)
      : activeId
        ? edge.source === activeId || edge.target === activeId
        : false;
    const dimmed = selectedIds.size || activeId
      ? !selectedNeighborhood.has(edge.source) || !selectedNeighborhood.has(edge.target)
      : false;

    drawEdge(ctx, from, to, compact ? "" : edge.label, highlighted, dimmed);
  }

  // 5. Draw nodes (viewport-culled)
  for (const node of visibleNodes) {
    const config = getNodeConfig(node.type);
    const isSelected = selectedIds.has(node.id);
    const isHovered = node.id === hoveredId;
    const dimmed = (selectedIds.size > 0 || hoveredId) ? !selectedNeighborhood.has(node.id) : false;

    const radius = node.radius * (isSelected ? 1.25 : isHovered ? 1.1 : 1);
    const alpha = dimmed ? 0.3 : 1;

    // Glow for selected (skipped when the graph is huge to save fill rate)
    if (isSelected && !skipShadows) {
      ctx.save();
      ctx.globalAlpha = 0.2;
      ctx.shadowColor = config.color;
      ctx.shadowBlur = 12;
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius * 1.5, 0, Math.PI * 2);
      ctx.fillStyle = config.color;
      ctx.fill();
      ctx.restore();
    }

    // Node fill (no per-node shadowBlur — that was the layout freeze culprit;
    // only the selected-node glow above uses shadow/glow on purpose)
    ctx.save();
    ctx.globalAlpha = alpha;
    drawShape(ctx, config.shape, node.x, node.y, radius);
    ctx.fillStyle = dimmed ? "#1e293b" : config.color;
    ctx.fill();

    // Border
    ctx.lineWidth = isSelected ? 2.5 : 1.5;
    ctx.strokeStyle = isSelected
      ? "#ffffff"
      : dimmed
        ? "#334155"
        : config.borderColor;
    ctx.stroke();
    ctx.restore();

    // Label (LOD-aware; selected and hovered labels always survive LOD)
    if ((!dimmed || isSelected) && (!hideLabels || isSelected || isHovered)) {
      drawLabel(ctx, node.label, node.x, node.y, cameraZoom);
    }
  }

  ctx.restore();

  // 6. Legend (compact mode)
  if (compact && nodes.length > 0) {
    const legendY = height - 28;
    ctx.font = "10px Inter, system-ui, sans-serif";
    let lx = 12;
    for (const cat of CATEGORY_ORDER) {
      const count = nodes.filter((n) => n.category === cat).length;
      if (count === 0) continue;
      ctx.fillStyle = CATEGORY_COLORS[cat];
      ctx.beginPath();
      ctx.arc(lx, legendY, 4, 0, Math.PI * 2);
      ctx.fill();
      lx += 10;
      ctx.fillStyle = "#86a99f";
      ctx.fillText(`${CATEGORY_LABELS[cat].split(" ")[0]} ${count}`, lx, legendY + 4);
      lx += ctx.measureText(`${CATEGORY_LABELS[cat].split(" ")[0]} ${count}`).width + 16;
    }
  }
}
