import type { CaseMonitor, GraphRead, SourceRead } from "../../types";

export type DashboardMetricTone = "neutral" | "success" | "warning" | "danger";

export interface DashboardMetric {
  key: string;
  label: string;
  value: string | number;
  tone?: DashboardMetricTone;
  description?: string;
}

export interface DashboardMetricInput {
  investigations: number;
  graph: GraphRead;
  sources: SourceRead[];
  monitor: CaseMonitor | null;
}

export function buildDashboardMetrics({
  investigations,
  graph,
  sources,
  monitor,
}: DashboardMetricInput): DashboardMetric[] {
  const entityCount = graph?.nodes?.length || monitor?.entity_count || 0;
  const relationshipCount = graph?.edges?.length || monitor?.relationship_count || 0;
  const sourceCount = sources?.length || monitor?.source_count || 0;
  const sealedCount = monitor?.sealed_count ?? 0;
  const custodyIntact = monitor?.custody_intact ?? null;

  return [
    {
      key: "investigations",
      label: "Investigations",
      value: investigations,
      tone: "neutral",
      description: "Total local investigations",
    },
    {
      key: "entities",
      label: "Entities",
      value: entityCount,
      tone: entityCount > 0 ? "success" : "neutral",
      description: "Verified entities in active case",
    },
    {
      key: "relationships",
      label: "Relationships",
      value: relationshipCount,
      tone: relationshipCount > 0 ? "success" : "neutral",
      description: "Verified relationships in active case",
    },
    {
      key: "evidence_sources",
      label: "Evidence sources",
      value: sourceCount,
      tone: sourceCount > 0 ? "success" : "neutral",
      description: "Sources and evidence items attached",
    },
    {
      key: "sealed_items",
      label: "Sealed items",
      value: sealedCount,
      tone: sealedCount > 0 ? "success" : "neutral",
      description: "Cryptographically sealed evidence",
    },
    {
      key: "custody_status",
      label: "Custody Status",
      value: custodyIntact === null ? "Unavailable" : custodyIntact ? "Intact" : "Review required",
      tone: custodyIntact === null ? "neutral" : custodyIntact ? "success" : "warning",
      description: "Evidence custody chain status",
    },
  ];
}

export function dashboardActionLabel(action: string): string {
  return action.replace(/[._-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
