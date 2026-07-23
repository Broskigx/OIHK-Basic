import type { CaseMonitor } from "../../types";

export interface DashboardMetric {
  label: string;
  value: number | string;
  change?: string;
}

export function buildDashboardMetrics(
  investigationCount: number,
  monitor: CaseMonitor | null,
): DashboardMetric[] {
  return [
    { label: "Investigations", value: investigationCount },
    { label: "Entities", value: monitor?.entity_count ?? "—" },
    { label: "Relationships", value: monitor?.relationship_count ?? "—" },
    { label: "Evidence sources", value: monitor?.source_count ?? "—" },
    { label: "Sealed items", value: monitor?.sealed_count ?? "—" },
  ];
}

export function dashboardActionLabel(action: string): string {
  return action.replace(/[._-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
