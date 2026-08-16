import { createElement } from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { DashboardSummary } from "../../types";
import { DashboardContent } from "./DashboardView";
import { buildDashboardMetrics, dashboardActionLabel } from "./dashboardModel";

function summary(overrides: Partial<DashboardSummary["counts"]> = {}): DashboardSummary {
  return {
    generated_at: "2026-08-11T00:00:00Z",
    counts: {
      active_investigations: 2,
      registered_evidence: 4,
      pending_tasks: null,
      tasks_available: false,
      connected_modules: 1,
      registered_modules: 2,
      ...overrides,
    },
    recent_investigations: [],
    recent_activity: [],
    modules: [],
  };
}

const noOp = vi.fn();

function renderDashboard(props: { summary: DashboardSummary | null; loading?: boolean; error?: string }) {
  return renderToString(createElement(DashboardContent, {
    summary: props.summary,
    loading: props.loading ?? false,
    error: props.error ?? "",
    storageStatus: null,
    localModelStatus: null,
    localModelLoading: false,
    onRetry: noOp,
    onRefreshLocalModel: noOp,
    onOpenCopilot: noOp,
    onNavigate: noOp,
    onOpenCase: noOp,
    onNewCase: noOp,
  }));
}

describe("dashboard metrics", () => {
  it("maps only API-provided counts", () => {
    expect(buildDashboardMetrics(summary()).map((metric) => metric.value)).toEqual([2, 4, "—", "1 / 2"]);
  });

  it("uses zero when a real task registry reports zero pending tasks", () => {
    const metrics = buildDashboardMetrics(summary({ tasks_available: true, pending_tasks: 0 }));
    expect(metrics.find((metric) => metric.key === "tasks")?.value).toBe(0);
  });

  it("formats audited actions without inventing descriptions", () => {
    expect(dashboardActionLabel("evidence.file_uploaded")).toBe("Evidence File Uploaded");
  });
});

describe("DashboardContent states", () => {
  it("renders a loading state without fake numbers", () => {
    const markup = renderDashboard({ summary: null, loading: true });
    expect(markup).toContain("Loading dashboard");
    expect(markup).not.toContain("1,248");
  });

  it("renders an actionable error state", () => {
    const markup = renderDashboard({ summary: null, error: "Backend unavailable" });
    expect(markup).toContain("Dashboard data is unavailable");
    expect(markup).toContain("Backend unavailable");
    expect(markup).toContain("Try again");
  });

  it("renders explicit empty states", () => {
    const markup = renderDashboard({ summary: summary({ active_investigations: 0, registered_evidence: 0, connected_modules: 0, registered_modules: 0 }) });
    expect(markup).toContain("No investigations yet");
    expect(markup).toContain("No linked modules");
    expect(markup).toContain("No recorded activity");
  });
});
