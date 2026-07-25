/**
 * GraphSpatialIndex — lightweight grid-based spatial index.
 * O(1) cell lookup for hit testing and viewport queries.
 * Much faster than O(n) linear scan for large graphs.
 */

import type { SpatialItem, ViewportBounds } from "./types";

const DEFAULT_CELL_SIZE = 80;

export class GraphSpatialIndex {
  private cellSize: number;
  private grid = new Map<string, SpatialItem[]>();
  private items = new Map<string, SpatialItem>();

  constructor(cellSize = DEFAULT_CELL_SIZE) {
    this.cellSize = cellSize;
  }

  /** Rebuild the entire grid from an array of items */
  rebuild(items: SpatialItem[]): void {
    this.grid.clear();
    this.items.clear();
    for (const item of items) {
      this.items.set(item.id, item);
      this._insert(item);
    }
  }

  /** Insert or update a single item */
  upsert(item: SpatialItem): void {
    const existing = this.items.get(item.id);
    if (existing) {
      this._remove(existing);
    }
    this.items.set(item.id, item);
    this._insert(item);
  }

  /** Remove a single item by id */
  remove(id: string): void {
    const item = this.items.get(id);
    if (!item) return;
    this._remove(item);
    this.items.delete(id);
  }

  /** Clear entire index */
  clear(): void {
    this.grid.clear();
    this.items.clear();
  }

  /** Find the closest item within `threshold` world-units of (x, y), with optional item filter */
  hitTest(
    x: number,
    y: number,
    threshold: number,
    filterFn?: (item: SpatialItem) => boolean,
  ): SpatialItem | null {
    let closest: SpatialItem | null = null;
    let minDist = threshold;

    const cells = this._getNearbyCells(x, y);
    for (const cellKey of cells) {
      const cell = this.grid.get(cellKey);
      if (!cell) continue;
      for (const item of cell) {
        if (filterFn && !filterFn(item)) continue;
        const dx = x - item.x;
        const dy = y - item.y;
        const dist = Math.sqrt(dx * dx + dy * dy) - item.radius;
        if (dist < minDist) {
          minDist = dist;
          closest = item;
        }
      }
    }
    return closest;
  }

  /** Return all items that overlap the given viewport bounds (for culling) */
  queryViewport(bounds: ViewportBounds): SpatialItem[] {
    const result: SpatialItem[] = [];
    const { x1, y1, x2, y2 } = bounds;
    const margin = 40; // extra margin to avoid pop-in

    const startCX = Math.floor((x1 - margin) / this.cellSize);
    const endCX = Math.floor((x2 + margin) / this.cellSize);
    const startCY = Math.floor((y1 - margin) / this.cellSize);
    const endCY = Math.floor((y2 + margin) / this.cellSize);

    const seen = new Set<string>();
    for (let cx = startCX; cx <= endCX; cx++) {
      for (let cy = startCY; cy <= endCY; cy++) {
        const cell = this.grid.get(`${cx},${cy}`);
        if (!cell) continue;
        for (const item of cell) {
          if (seen.has(item.id)) continue;
          seen.add(item.id);
          result.push(item);
        }
      }
    }
    return result;
  }

  /** Query all items within a rectangular region (for box selection) */
  queryRect(x1: number, y1: number, x2: number, y2: number): SpatialItem[] {
    return this.queryViewport({ x1: Math.min(x1, x2), y1: Math.min(y1, y2), x2: Math.max(x1, x2), y2: Math.max(y1, y2) });
  }

  /** Get all items */
  allItems(): SpatialItem[] {
    return Array.from(this.items.values());
  }

  /** Total number of items */
  get size(): number {
    return this.items.size;
  }

  // ── Private helpers ──

  private _cellKey(x: number, y: number): string {
    return `${Math.floor(x / this.cellSize)},${Math.floor(y / this.cellSize)}`;
  }

  private _insert(item: SpatialItem): void {
    const key = this._cellKey(item.x, item.y);
    let cell = this.grid.get(key);
    if (!cell) {
      cell = [];
      this.grid.set(key, cell);
    }
    cell.push(item);
  }

  private _remove(item: SpatialItem): void {
    const key = this._cellKey(item.x, item.y);
    const cell = this.grid.get(key);
    if (!cell) return;
    const idx = cell.indexOf(item);
    if (idx >= 0) cell.splice(idx, 1);
    if (cell.length === 0) this.grid.delete(key);
  }

  /** Returns up to 9 cell keys around a point (3×3 neighborhood) */
  private _getNearbyCells(x: number, y: number): string[] {
    const cx = Math.floor(x / this.cellSize);
    const cy = Math.floor(y / this.cellSize);
    const keys: string[] = [];
    for (let dx = -1; dx <= 1; dx++) {
      for (let dy = -1; dy <= 1; dy++) {
        keys.push(`${cx + dx},${cy + dy}`);
      }
    }
    return keys;
  }
}
