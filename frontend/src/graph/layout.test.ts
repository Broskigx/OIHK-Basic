import { describe, expect, it } from "vitest";
import { GraphLayoutEngine } from "./layout";
import type { GraphRead } from "../types";

describe("GraphLayoutEngine", () => {
  it("keeps large graph simulation finite with the adaptive spatial layout", () => {
    const graph: GraphRead = {
      nodes: Array.from({ length: 1200 }, (_, index) => ({
        id: `node-${index}`,
        label: `Node ${index}`,
        type: index % 3 === 0 ? "domain" : "note",
        confidence: 0.8,
        source_ids: [],
        value: `node-${index}`,
        properties: {},
        notes: "",
      })),
      edges: Array.from({ length: 1199 }, (_, index) => ({
        id: `edge-${index}`,
        source: `node-${index}`,
        target: `node-${index + 1}`,
        label: "linked",
        confidence: 0.7,
        source_ids: [],
      })),
    };
    const engine = new GraphLayoutEngine();
    engine.init(graph);
    engine.start();
    expect(engine.tick(graph)).toBe(true);
    expect(engine.nodes.every((node) => Number.isFinite(node.x) && Number.isFinite(node.y))).toBe(true);
  });
});
