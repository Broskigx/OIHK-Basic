import { describe, expect, it } from "vitest";
import type { CaseMonitor, GraphRead, SourceRead } from "../../types";
import { buildDashboardMetrics, dashboardActionLabel } from "./dashboardModel";

const emptyGraph: GraphRead = { nodes: [], edges: [] };
const emptySources: SourceRead[] = [];

function monitorWith(overrides: Partial<CaseMonitor> = {}): CaseMonitor {
  return {
    case_id: "case-1",
    generated_at: "2024-01-01T00:00:00Z",
    status: "active",
    source_count: 0,
    entity_count: 0,
    relationship_count: 0,
    sealed_count: 0,
    custody_intact: true,
    active_search_runs: 0,
    latest_activity_at: null,
    source_mix: {},
    risk_flags: [],
    recent_events: [],
    ...overrides,
  };
}

describe("buildDashboardMetrics", () => {
  it("returns honest unavailable values when no data exists", () => {
    const metrics = buildDashboardMetrics({
      investigations: 2,
      graph: emptyGraph,
      sources: emptySources,
      monitor: null,
    });
    expect(metrics.map((m) => ({ key: m.key, value: m.value }))).toEqual([
      { key: "investigations", value: 2 },
      { key: "entities", value: 0 },
      { key: "relationships", value: 0 },
      { key: "evidence_sources", value: 0 },
      { key: "sealed_items", value: 0 },
      { key: "custody_status", value: "Unavailable" },
    ]);
  });

  it("derives counts from graph nodes and edges", () => {
    const graph: GraphRead = {
      nodes: [
        { id: "n1", label: "A", type: "person", confidence: 1, source_ids: [] },
        { id: "n2", label: "B", type: "person", confidence: 1, source_ids: [] },
        { id: "n3", label: "C", type: "domain", confidence: 1, source_ids: [] },
      ],
      edges: [
        { id: "e1", source: "n1", target: "n2", label: "knows", confidence: 1, source_ids: [] },
        { id: "e2", source: "n2", target: "n3", label: "owns", confidence: 1, source_ids: [] },
      ],
    };
    const metrics = buildDashboardMetrics({
      investigations: 1,
      graph,
      sources: emptySources,
      monitor: null,
    });
    expect(metrics.find((m) => m.key === "entities")?.value).toBe(3);
    expect(metrics.find((m) => m.key === "relationships")?.value).toBe(2);
  });

  it("counts evidence sources from the sources array", () => {
    const sources = [
      { id: "s1", case_id: "c1", title: "Source 1", kind: "web", url: "https://example.com/1", citation: "", license: "", reliability: 0.8, robot_compliant: true, collected_at: "2024-01-01T00:00:00Z" },
      { id: "s2", case_id: "c1", title: "Source 2", kind: "web", url: "https://example.com/2", citation: "", license: "", reliability: 0.8, robot_compliant: true, collected_at: "2024-01-01T00:00:00Z" },
    ] as SourceRead[];
    const metrics = buildDashboardMetrics({
      investigations: 1,
      graph: emptyGraph,
      sources,
      monitor: null,
    });
    expect(metrics.find((m) => m.key === "evidence_sources")?.value).toBe(2);
  });

  it("falls back to monitor counts when graph/sources are empty", () => {
    const monitor = monitorWith({
      entity_count: 7,
      relationship_count: 5,
      source_count: 3,
      sealed_count: 2,
    });
    const metrics = buildDashboardMetrics({
      investigations: 1,
      graph: emptyGraph,
      sources: emptySources,
      monitor,
    });
    expect(metrics.map((m) => m.value)).toEqual([1, 7, 5, 3, 2, "Intact"]);
  });

  it("prefers real graph/sources counts over monitor counts", () => {
    const graph: GraphRead = {
      nodes: [{ id: "n1", label: "A", type: "person", confidence: 1, source_ids: [] }],
      edges: [{ id: "e1", source: "n1", target: "n1", label: "self", confidence: 1, source_ids: [] }],
    };
    const sources = [{ id: "s1", case_id: "c1", title: "Source 1", kind: "web", url: "https://example.com/1", citation: "", license: "", reliability: 0.8, robot_compliant: true, collected_at: "2024-01-01T00:00:00Z" }] as SourceRead[];
    const monitor = monitorWith({ entity_count: 99, relationship_count: 88, source_count: 77 });
    const metrics = buildDashboardMetrics({ investigations: 1, graph, sources, monitor });
    expect(metrics.find((m) => m.key === "entities")?.value).toBe(1);
    expect(metrics.find((m) => m.key === "relationships")?.value).toBe(1);
    expect(metrics.find((m) => m.key === "evidence_sources")?.value).toBe(1);
  });

  it("never returns UUID or object-like values", () => {
    const metrics = buildDashboardMetrics({
      investigations: 1,
      graph: emptyGraph,
      sources: emptySources,
      monitor: null,
    });
    for (const metric of metrics) {
      expect(typeof metric.value).not.toBe("object");
      expect(String(metric.value)).not.toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
    }
  });

  it("reports review required when custody is not intact", () => {
    const metrics = buildDashboardMetrics({
      investigations: 1,
      graph: emptyGraph,
      sources: emptySources,
      monitor: monitorWith({ custody_intact: false }),
    });
    expect(metrics.find((m) => m.key === "custody_status")?.value).toBe("Review required");
  });
});

describe("dashboardActionLabel", () => {
  it("renders audit actions as readable labels", () => {
    expect(dashboardActionLabel("case.monitor_updated")).toBe("Case Monitor Updated");
  });
});
