/**
 * GraphLayoutEngine — force-directed layout with category-based clustering.
 * Pure logic, no React. Designed to be run in requestAnimationFrame or Web Worker.
 *
 * Physically inspired: adaptive repulsion, attraction (edges),
 * category cohesion, center gravity, damping, and convergence.
 */

import type { GraphRead } from "../types";
import { type LayoutNode } from "./types";
import { getCategory, CATEGORY_ORDER } from "../components/graphTypes";

// ── Tunable physics constants ──
const REPULSION = 8000;
const ATTRACTION = 0.005;
const DAMPING = 0.85;
const CENTER_GRAVITY = 0.01;
const CATEGORY_ATTRACTION = 0.003;
const MAX_SPEED = 8;
const CONVERGENCE_THRESHOLD = 0.05;
const CONVERGENCE_FRAMES = 20; // must be below threshold for this many frames
const EXACT_REPULSION_LIMIT = 500;
const REPULSION_CELL_SIZE = 120;

/** Compute a visual radius for a node based on type + degree */
export function nodeRadius(type: string, degree: number, maxDegree: number): number {
  const base = type === "name" || type === "organization" ? 10 : 8;
  const degreeBoost = maxDegree > 0 ? (degree / maxDegree) * 6 : 0;
  return Math.max(base, Math.min(22, base + degreeBoost));
}

/** Pure distance helper */
export function distance(x1: number, y1: number, x2: number, y2: number): number {
  const dx = x2 - x1;
  const dy = y2 - y1;
  return Math.sqrt(dx * dx + dy * dy);
}

export class GraphLayoutEngine {
  nodes: LayoutNode[] = [];
  private running = false;
  private convergedFrames = 0;
  private _converged = false;
  private _elapsed = 0;

  /** Build initial layout positions from graph data, preserving old positions if possible */
  init(graph: GraphRead, oldNodes?: LayoutNode[]): void {
    const degree = new Map<string, number>();
    for (const edge of graph.edges) {
      degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
      degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
    }
    const maxDeg = Math.max(1, ...degree.values());

    // Category ring positions
    const categories = new Map<string, { cx: number; cy: number; members: string[] }>();
    for (const cat of CATEGORY_ORDER) {
      const angle = (CATEGORY_ORDER.indexOf(cat) / CATEGORY_ORDER.length) * Math.PI * 2 - Math.PI / 2;
      categories.set(cat, { cx: Math.cos(angle) * 180, cy: Math.sin(angle) * 180, members: [] });
    }
    for (const node of graph.nodes) {
      const cat = getCategory(node.type);
      const group = categories.get(cat) ?? categories.get("other")!;
      group.members.push(node.id);
    }

    // Preserve old positions when possible
    const oldPos = new Map(oldNodes?.map((n) => [n.id, { x: n.x, y: n.y, pinned: n.pinned }]) ?? []);

    this.nodes = graph.nodes.map((node) => {
      const cat = getCategory(node.type);
      const group = categories.get(cat) ?? categories.get("other")!;
      const deg = degree.get(node.id) ?? 0;
      const old = oldPos.get(node.id);
      const memberIndex = group.members.indexOf(node.id);
      const angleOffset = (memberIndex / Math.max(1, group.members.length)) * Math.PI * 2;
      const spawnAngle = (CATEGORY_ORDER.indexOf(cat) / CATEGORY_ORDER.length) * Math.PI * 2 - Math.PI / 2;
      const radiusFromCenter = 20 + (memberIndex % 10) * 22;

      return {
        id: node.id,
        x: old?.x ?? group.cx + Math.cos(angleOffset + spawnAngle) * radiusFromCenter * 0.4,
        y: old?.y ?? group.cy + Math.sin(angleOffset + spawnAngle) * radiusFromCenter * 0.4,
        vx: 0,
        vy: 0,
        radius: nodeRadius(node.type, deg, maxDeg),
        type: node.type,
        label: node.label,
        category: cat,
        confidence: node.confidence,
        pinned: old?.pinned ?? false,
        _iter: 0,
      };
    });

    this._converged = false;
    this.convergedFrames = 0;
    this._elapsed = 0;
  }

  /** Perform one simulation step. Returns true if the layout is still active/animating. */
  tick(graph: GraphRead): boolean {
    if (!this.running || this._converged) return false;

    const nodes = this.nodes;
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));

    // Damping
    for (const node of nodes) {
      if (node.pinned) continue;
      node.vx *= DAMPING;
      node.vy *= DAMPING;
    }

    const repelPair = (a: LayoutNode, b: LayoutNode) => {
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const force = REPULSION / (dist * dist);
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      if (!a.pinned) { a.vx += fx; a.vy += fy; }
      if (!b.pinned) { b.vx -= fx; b.vy -= fy; }
    };

    if (nodes.length <= EXACT_REPULSION_LIMIT) {
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) repelPair(nodes[i], nodes[j]);
      }
    } else {
      // Large graphs use a uniform spatial grid. Only nearby cells need exact
      // collision repulsion; attraction and gravity provide the global shape.
      const grid = new Map<string, LayoutNode[]>();
      for (const node of nodes) {
        const x = Math.floor(node.x / REPULSION_CELL_SIZE);
        const y = Math.floor(node.y / REPULSION_CELL_SIZE);
        const key = `${x}:${y}`;
        const cell = grid.get(key);
        if (cell) cell.push(node);
        else grid.set(key, [node]);
      }
      const visited = new Set<string>();
      for (const node of nodes) {
        const cellX = Math.floor(node.x / REPULSION_CELL_SIZE);
        const cellY = Math.floor(node.y / REPULSION_CELL_SIZE);
        for (let x = cellX - 1; x <= cellX + 1; x++) {
          for (let y = cellY - 1; y <= cellY + 1; y++) {
            for (const other of grid.get(`${x}:${y}`) ?? []) {
              if (node.id === other.id) continue;
              const pairKey = node.id < other.id ? `${node.id}|${other.id}` : `${other.id}|${node.id}`;
              if (visited.has(pairKey)) continue;
              visited.add(pairKey);
              repelPair(node, other);
            }
          }
        }
      }
    }

    // Attraction along edges
    for (const edge of graph.edges) {
      const source = nodeMap.get(edge.source);
      const target = nodeMap.get(edge.target);
      if (!source || !target) continue;
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const dist = Math.max(1, distance(source.x, source.y, target.x, target.y));
      const force = (dist - (source.radius + target.radius + 20)) * ATTRACTION;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      if (!source.pinned) { source.vx += fx; source.vy += fy; }
      if (!target.pinned) { target.vx -= fx; target.vy -= fy; }
    }

    // Category cohesion uses one centroid pass instead of an all-pairs scan.
    const categoryCentroids = new Map<string, { x: number; y: number; count: number }>();
    for (const node of nodes) {
      const centroid = categoryCentroids.get(node.category) ?? { x: 0, y: 0, count: 0 };
      centroid.x += node.x;
      centroid.y += node.y;
      centroid.count += 1;
      categoryCentroids.set(node.category, centroid);
    }
    for (const node of nodes) {
      if (node.pinned) continue;
      const centroid = categoryCentroids.get(node.category);
      if (centroid && centroid.count > 1) {
        const count = centroid.count - 1;
        const cx = (centroid.x - node.x) / count;
        const cy = (centroid.y - node.y) / count;
        node.vx += (cx - node.x) * CATEGORY_ATTRACTION;
        node.vy += (cy - node.y) * CATEGORY_ATTRACTION;
      }
    }

    // Center gravity
    for (const node of nodes) {
      if (node.pinned) continue;
      node.vx -= node.x * CENTER_GRAVITY;
      node.vy -= node.y * CENTER_GRAVITY;
    }

    // Apply velocity with clamping + convergence tracking
    let maxVelocity = 0;
    for (const node of nodes) {
      if (node.pinned) continue;
      const speed = Math.sqrt(node.vx * node.vx + node.vy * node.vy);
      if (speed > MAX_SPEED) {
        node.vx = (node.vx / speed) * MAX_SPEED;
        node.vy = (node.vy / speed) * MAX_SPEED;
      }
      node.x += node.vx;
      node.y += node.vy;
      node._iter++;
      if (Math.abs(node.vx) + Math.abs(node.vy) > maxVelocity) {
        maxVelocity = Math.abs(node.vx) + Math.abs(node.vy);
      }
    }

    this._elapsed++;

    // Convergence detection
    if (maxVelocity < CONVERGENCE_THRESHOLD) {
      this.convergedFrames++;
      if (this.convergedFrames >= CONVERGENCE_FRAMES) {
        this._converged = true;
        return false;
      }
    } else {
      this.convergedFrames = 0;
    }

    return true;
  }

  /** Start the layout simulation */
  start(): void {
    this.running = true;
    this._converged = false;
    this.convergedFrames = 0;
  }

  /** Stop the layout simulation */
  stop(): void {
    this.running = false;
  }

  /** Whether the layout has converged */
  get converged(): boolean {
    return this._converged;
  }

  /** Whether the layout is running */
  get isRunning(): boolean {
    return this.running;
  }

  /** Get current node positions */
  getNodePositions(): LayoutNode[] {
    return this.nodes;
  }

  /** Set a node's pinned state */
  setPinned(nodeId: string, pinned: boolean): void {
    const node = this.nodes.find((n) => n.id === nodeId);
    if (node) {
      node.pinned = pinned;
      if (pinned) this._converged = false; // unpause if interacting
    }
  }

  /** Update node positions from external source (e.g., hierarchy layout) */
  applyPositions(positions: Record<string, { x: number; y: number }>): void {
    for (const node of this.nodes) {
      const pos = positions[node.id];
      if (pos) {
        node.x = pos.x;
        node.y = pos.y;
        node.vx = 0;
        node.vy = 0;
      }
    }
    this._converged = true;
  }
}
