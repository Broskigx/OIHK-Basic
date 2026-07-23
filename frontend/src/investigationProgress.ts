import type { AutoStreamEvent } from "./types";

export type InvestigationProgress = {
  active: boolean;
  pct: number;
  step: string;
  label: string;
  provider?: string;
  queries: string[];
  hits: { title: string; url?: string; source_name?: string }[];
  entityCount: number;
  failed: boolean;
};

export const initialProgress: InvestigationProgress = {
  active: true,
  pct: 0,
  step: "case",
  label: "Iniciando…",
  queries: [],
  hits: [],
  entityCount: 0,
  failed: false,
};

export function reduceProgressEvent(base: InvestigationProgress, event: AutoStreamEvent): InvestigationProgress {
  const next: InvestigationProgress = { ...base };
  if (typeof event.progress === "number") next.pct = Math.round(event.progress * 100);
  if (event.step) next.step = event.step;
  if (event.label) next.label = event.label;
  if (event.provider) next.provider = event.provider;
  if (event.queries) next.queries = event.queries;
  if (event.phase === "hit") {
    next.hits = [
      { title: event.label ?? "", url: event.url, source_name: event.source_name },
      ...base.hits,
    ].slice(0, 8);
  }
  if (event.phase === "page") {
    next.hits = [
      { title: event.label ?? "", url: event.url, source_name: "página leída" },
      ...base.hits,
    ].slice(0, 8);
  }
  if (typeof event.entity_total === "number") next.entityCount = event.entity_total;
  if (event.phase === "error") next.failed = true;
  return next;
}
