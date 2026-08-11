import { describe, expect, it } from "vitest";
import type { GraphRead } from "../../types";
import { filterGraphForView } from "./graphFilters";

const graph: GraphRead = {
  nodes: [
    { id: "person", label: "Person", type: "name", confidence: 0.8, source_ids: ["source-1"], properties: {}, notes: "" },
    { id: "email", label: "person@example.test", type: "email", confidence: 0.7, source_ids: ["source-1"], properties: {}, notes: "" },
    { id: "note", label: "Unattributed note", type: "note", confidence: 0.5, source_ids: [], properties: {}, notes: "" },
  ],
  edges: [
    { id: "edge-1", source: "person", target: "email", label: "uses", confidence: 0.8, source_ids: ["source-1"] },
    { id: "edge-2", source: "person", target: "note", label: "mentions", confidence: 0.5, source_ids: [] },
  ],
};

describe("filterGraphForView", () => {
  it("filters by type without mutating the stored graph", () => {
    const filtered = filterGraphForView(graph, "email", "all");
    expect(filtered.nodes.map((node) => node.id)).toEqual(["email"]);
    expect(filtered.edges).toEqual([]);
    expect(graph.nodes).toHaveLength(3);
    expect(graph.edges).toHaveLength(2);
  });

  it("keeps only complete relationships when filtering by provenance", () => {
    const sourced = filterGraphForView(graph, "all", "with-sources");
    expect(sourced.nodes.map((node) => node.id)).toEqual(["person", "email"]);
    expect(sourced.edges.map((edge) => edge.id)).toEqual(["edge-1"]);

    const unsourced = filterGraphForView(graph, "all", "without-sources");
    expect(unsourced.nodes.map((node) => node.id)).toEqual(["note"]);
    expect(unsourced.edges).toEqual([]);
  });
});
