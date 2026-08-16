import type { AuditEvent, SearchRun, SourceRead, TargetPhoto } from "../../types";

export const TIMELINE_EVENT_TYPES = ["audit", "source", "search_run", "target_photo"] as const;

export type TimelineEventType = (typeof TIMELINE_EVENT_TYPES)[number];

type TimelineEventBase<TType extends TimelineEventType, TRecord> = {
  key: string;
  type: TType;
  occurredAt: string;
  caseId: string | null;
  record: TRecord;
};

type TimelineAuditEvent = TimelineEventBase<"audit", AuditEvent>;
type TimelineSourceEvent = TimelineEventBase<"source", SourceRead>;
type TimelineSearchRunEvent = TimelineEventBase<"search_run", SearchRun>;
type TimelineTargetPhotoEvent = TimelineEventBase<"target_photo", TargetPhoto>;

export type TimelineEvent =
  | TimelineAuditEvent
  | TimelineSourceEvent
  | TimelineSearchRunEvent
  | TimelineTargetPhotoEvent;

export type TimelineInput = {
  auditEvents: readonly AuditEvent[];
  sources: readonly SourceRead[];
  searchRuns: readonly SearchRun[];
  targetPhotos: readonly TargetPhoto[];
};

export type TimelineDayGroup = {
  date: string | null;
  events: TimelineEvent[];
};

function timestampValue(timestamp: string): number {
  const parsed = Date.parse(timestamp);
  return Number.isFinite(parsed) ? parsed : Number.NEGATIVE_INFINITY;
}

export function sortTimelineEventsDescending(events: readonly TimelineEvent[]): TimelineEvent[] {
  return [...events].sort(
    (left, right) => timestampValue(right.occurredAt) - timestampValue(left.occurredAt),
  );
}

export function buildTimelineEvents({
  auditEvents,
  sources,
  searchRuns,
  targetPhotos,
}: TimelineInput): TimelineEvent[] {
  const auditTimelineEvents: TimelineAuditEvent[] = auditEvents.map((record) => ({
    key: `audit:${record.id}`,
    type: "audit",
    occurredAt: record.created_at,
    caseId: record.case_id,
    record,
  }));

  const sourceTimelineEvents: TimelineSourceEvent[] = sources.map((record) => ({
    key: `source:${record.id}`,
    type: "source",
    occurredAt: record.collected_at,
    caseId: record.case_id,
    record,
  }));

  const searchRunTimelineEvents: TimelineSearchRunEvent[] = searchRuns.map((record) => ({
    key: `search-run:${record.id}`,
    type: "search_run",
    occurredAt: record.created_at,
    caseId: record.case_id,
    record,
  }));

  const targetPhotoTimelineEvents: TimelineTargetPhotoEvent[] = targetPhotos.map((record) => ({
    key: `target-photo:${record.id}`,
    type: "target_photo",
    occurredAt: record.created_at,
    caseId: record.case_id,
    record,
  }));

  return sortTimelineEventsDescending([
    ...auditTimelineEvents,
    ...sourceTimelineEvents,
    ...searchRunTimelineEvents,
    ...targetPhotoTimelineEvents,
  ]);
}

export function filterTimelineEvents(
  events: readonly TimelineEvent[],
  selectedTypes: ReadonlySet<TimelineEventType> | readonly TimelineEventType[],
): TimelineEvent[] {
  const typeSet = selectedTypes instanceof Set ? selectedTypes : new Set(selectedTypes);
  return sortTimelineEventsDescending(events.filter((event) => typeSet.has(event.type)));
}

export function groupTimelineEventsByDay(events: readonly TimelineEvent[]): TimelineDayGroup[] {
  const groups = new Map<string | null, TimelineEvent[]>();

  for (const event of sortTimelineEventsDescending(events)) {
    const timestamp = timestampValue(event.occurredAt);
    const localDate = new Date(timestamp);
    const date = Number.isFinite(timestamp)
      ? `${localDate.getFullYear()}-${String(localDate.getMonth() + 1).padStart(2, "0")}-${String(localDate.getDate()).padStart(2, "0")}`
      : null;
    const group = groups.get(date);

    if (group) {
      group.push(event);
    } else {
      groups.set(date, [event]);
    }
  }

  return [...groups].map(([date, groupedEvents]) => ({ date, events: groupedEvents }));
}

export function serializeTimelineEvents(events: readonly TimelineEvent[]): string {
  return JSON.stringify(sortTimelineEventsDescending(events), null, 2);
}
