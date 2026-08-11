import { describe, expect, it } from "vitest";
import type { GraphNode } from "../../types";
import { searchGraphNodes } from "./graphSearch";

const nodes: GraphNode[] = [
  { id: "entity-001", label: "Example Person", value: "Example Person", type: "person", confidence: .8, source_ids: [], properties: { alias: "observer", email: "person@example.test" } },
  { id: "entity-002", label: "example.test", value: "example.test", type: "domain", confidence: .8, source_ids: ["source-1"], properties: { ip: "192.0.2.5" } },
];

describe("searchGraphNodes", () => {
  it("searches labels, values and ids", () => {
    expect(searchGraphNodes(nodes, "Example Person")[0].id).toBe("entity-001");
    expect(searchGraphNodes(nodes, "entity-002")[0].id).toBe("entity-002");
  });

  it("searches real aliases, email, domain and IP properties", () => {
    expect(searchGraphNodes(nodes, "observer")[0].id).toBe("entity-001");
    expect(searchGraphNodes(nodes, "person@example.test")[0].id).toBe("entity-001");
    expect(searchGraphNodes(nodes, "192.0.2.5")[0].id).toBe("entity-002");
  });

  it("returns no results for blank or unmatched queries", () => {
    expect(searchGraphNodes(nodes, " ")).toEqual([]);
    expect(searchGraphNodes(nodes, "missing")).toEqual([]);
  });
});
