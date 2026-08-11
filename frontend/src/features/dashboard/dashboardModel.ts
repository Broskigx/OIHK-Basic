import type { DashboardSummary } from "../../types";

export type DashboardMetric = {
  key: "investigations" | "evidence" | "tasks" | "modules";
  label: string;
  value: number | string;
  detail: string;
  tone: "positive" | "neutral" | "warning";
};

export function buildDashboardMetrics(summary: DashboardSummary): DashboardMetric[] {
  const { counts } = summary;
  return [
    {
      key: "investigations",
      label: "Active investigations",
      value: counts.active_investigations,
      detail: "Authorized active records",
      tone: counts.active_investigations > 0 ? "positive" : "neutral",
    },
    {
      key: "evidence",
      label: "Registered evidence",
      value: counts.registered_evidence,
      detail: "Managed evidence files",
      tone: counts.registered_evidence > 0 ? "positive" : "neutral",
    },
    {
      key: "tasks",
      label: "Pending tasks",
      value: counts.tasks_available ? (counts.pending_tasks ?? 0) : "—",
      detail: counts.tasks_available ? "Open task records" : "Task registry not available",
      tone: counts.tasks_available && (counts.pending_tasks ?? 0) > 0 ? "warning" : "neutral",
    },
    {
      key: "modules",
      label: "Connected modules",
      value: counts.registered_modules > 0
        ? `${counts.connected_modules} / ${counts.registered_modules}`
        : 0,
      detail: counts.registered_modules > 0 ? "READY or BUSY" : "No linked modules",
      tone: counts.connected_modules > 0 ? "positive" : "neutral",
    },
  ];
}

export function dashboardActionLabel(action: string): string {
  return action
    .replace(/_/g, " ")
    .replace(/\./g, " ")
    .replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}
