import { describe, expect, it } from "vitest";
import type { GraphRead } from "../../types";
import { connectionsLayout, graphForView, hierarchyLayout } from "./graphModes";

const graph: GraphRead = {
  nodes: [
    { id: "root", label: "Root", type: "name", confidence: 1, source_ids: [] },
    { id: "child-a", label: "Child A", type: "email", confidence: 0.9, source_ids: [] },
    { id: "child-b", label: "Child B", type: "domain", confidence: 0.8, source_ids: [] },
    { id: "grandchild", label: "Grandchild", type: "ip", confidence: 0.7, source_ids: [] },
    { id: "isolated", label: "Isolated", type: "note", confidence: 0.6, source_ids: [] },
  ],
  edges: [
    { id: "e1", source: "root", target: "child-a", label: "owns", confidence: 1, source_ids: [] },
    { id: "e2", source: "root", target: "child-b", label: "uses", confidence: 0.9, source_ids: [] },
    { id: "e3", source: "child-a", target: "grandchild", label: "resolves", confidence: 0.8, source_ids: [] },
  ],
};

describe("graph view models", () => {
  it("builds a focused one-hop connection view", () => {
    const focused = graphForView(graph, "connections", "child-a");

    expect(focused.nodes.map((node) => node.id).sort()).toEqual(["child-a", "grandchild", "root"]);
    expect(focused.edges.map((edge) => edge.id).sort()).toEqual(["e1", "e3"]);
  });

  it("removes isolated nodes from the general connection view", () => {
    const connected = graphForView(graph, "connections");

    expect(connected.nodes.some((node) => node.id === "isolated")).toBe(false);
    expect(connected.edges).toHaveLength(3);
  });

  it("places parents above their directed children", () => {
    const layout = hierarchyLayout(graph);

    expect(layout.root.level).toBe(0);
    expect(layout["child-a"].level).toBe(1);
    expect(layout.grandchild.level).toBe(2);
    expect(layout.root.y).toBeLessThan(layout["child-a"].y);
    expect(layout["child-a"].y).toBeLessThan(layout.grandchild.y);
  });

  it("centers the active entity in connection mode", () => {
    const focused = graphForView(graph, "connections", "child-a");
    const layout = connectionsLayout(focused, "child-a");

    expect(layout["child-a"]).toEqual({ x: 0, y: 0, level: 0 });
    expect(layout.root.level).toBe(1);
    expect(layout.grandchild.level).toBe(1);
  });
});
