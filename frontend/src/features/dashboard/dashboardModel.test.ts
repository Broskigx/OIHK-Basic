import { describe, expect, it } from "vitest";
import type { CaseMonitor } from "../../types";
import { buildDashboardMetrics, dashboardActionLabel } from "./dashboardModel";

describe("dashboard model", () => {
  it("does not invent monitor counts while data is unavailable", () => {
    expect(buildDashboardMetrics(2, null)).toEqual([
      { label: "Investigations", value: 2 },
      { label: "Entities", value: "—" },
      { label: "Relationships", value: "—" },
      { label: "Evidence sources", value: "—" },
      { label: "Sealed items", value: "—" },
    ]);
  });

  it("maps the live case monitor to dashboard metrics", () => {
    const monitor = {
      entity_count: 7,
      relationship_count: 5,
      source_count: 3,
      sealed_count: 2,
    } as CaseMonitor;

    expect(buildDashboardMetrics(1, monitor).map((metric) => metric.value)).toEqual([1, 7, 5, 3, 2]);
  });

  it("renders audit actions as readable labels", () => {
    expect(dashboardActionLabel("case.monitor_updated")).toBe("Case Monitor Updated");
  });
});
