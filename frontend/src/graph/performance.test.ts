import { describe, expect, it } from "vitest";
import { GraphLayoutEngine } from "./layout";
import { GraphSpatialIndex } from "./spatial";
import { fitToView } from "./camera";
import type { GraphRead } from "../types";

function buildGraph(nodeCount: number, chainLength: number): GraphRead {
  const nodes = Array.from({ length: nodeCount }, (_, index) => ({
    id: `node-${index}`,
    label: `Node ${index}`,
    type: index % 4 === 0 ? "domain" : index % 4 === 1 ? "hash" : "note",
    confidence: 0.8,
    source_ids: [],
    value: `node-${index}`,
    properties: {},
    notes: "",
  }));
  const edges = Array.from({ length: chainLength }, (_, index) => ({
    id: `edge-${index}`,
    source: `node-${index % nodeCount}`,
    target: `node-${(index + 1) % nodeCount}`,
    label: "linked",
    confidence: 0.7,
    source_ids: [],
  }));
  return { nodes, edges };
}

function layoutFiniteAfterTicks(graph: GraphRead, maxTicks: number): boolean {
  const engine = new GraphLayoutEngine();
  engine.init(graph);
  engine.start();
  for (let tick = 0; tick < maxTicks; tick += 1) {
    engine.tick(graph);
    if (engine.converged) break;
  }
  return engine.nodes.every((node) => Number.isFinite(node.x) && Number.isFinite(node.y));
}

describe("graph performance degradation", () => {
  it("keeps a small graph (50 nodes) finite and fast", { timeout: 30_000 }, () => {
    const graph = buildGraph(50, 60);
    expect(layoutFiniteAfterTicks(graph, 200)).toBe(true);
    const engine = new GraphLayoutEngine();
    engine.init(graph);
    engine.start();
    for (let tick = 0; tick < 200; tick += 1) engine.tick(graph);
    const settled = engine.nodes.every(
      (node) => Math.abs(node.x) < 1_000_000 && Math.abs(node.y) < 1_000_000,
    );
    expect(settled).toBe(true);
  });

  it("keeps a medium graph (500 nodes) finite with the adaptive spatial layout", { timeout: 60_000 }, () => {
    const graph = buildGraph(500, 700);
    expect(layoutFiniteAfterTicks(graph, 400)).toBe(true);
  });

  it("keeps a large graph (2500 nodes) finite with the adaptive spatial layout", { timeout: 120_000 }, () => {
    const graph = buildGraph(2500, 3000);
    expect(layoutFiniteAfterTicks(graph, 600)).toBe(true);
  });

  it("resolves spatial hit tests correctly for a large graph", () => {
    const index = new GraphSpatialIndex(80);
    const items = Array.from({ length: 1000 }, (_, i) => ({
      id: `n${i}`,
      x: (i % 100) * 40,
      y: Math.floor(i / 100) * 40,
      radius: 8,
    }));
    index.rebuild(items);
    const target = items[550];
    const hit = index.hitTest(target.x, target.y, 12);
    expect(hit?.id).toBe("n550");
    expect(index.size).toBe(1000);
  });

  it("computes a bounded fit-to-view for large graphs", () => {
    const graph = buildGraph(2500, 3000);
    const points = graph.nodes.map((node) => ({ x: node.id.length * 10, y: node.id.length * 5 }));
    const camera = fitToView(points, 1920, 1080);
    expect(Number.isFinite(camera.x)).toBe(true);
    expect(Number.isFinite(camera.y)).toBe(true);
    expect(camera.zoom).toBeGreaterThanOrEqual(0.1);
    expect(camera.zoom).toBeLessThanOrEqual(4);
  });
});
