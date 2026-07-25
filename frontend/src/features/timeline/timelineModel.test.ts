import { describe, expect, it } from "vitest";
import type { AuditEvent, SearchRun, SourceRead, TargetPhoto } from "../../types";
import {
  buildTimelineEvents,
  filterTimelineEvents,
  groupTimelineEventsByDay,
  serializeTimelineEvents,
  sortTimelineEventsDescending,
  type TimelineEvent,
} from "./timelineModel";

const audit: AuditEvent = {
  id: 7,
  actor: "analyst@example.test",
  action: "case.updated",
  case_id: "case-1",
  payload: { field: "scope_statement" },
  created_at: "2026-07-15T15:00:00Z",
};

const source: SourceRead = {
  id: "source-1",
  case_id: "case-1",
  title: "Registro mercantil",
  kind: "registry",
  url: "https://example.test/record",
  citation: "Registro 42",
  license: "official-record",
  reliability: 0.92,
  robot_compliant: true,
  collected_at: "2026-07-15T14:00:00Z",
};

const searchRun: SearchRun = {
  id: "run-1",
  case_id: "case-1",
  target_id: "target-1",
  status: "completed",
  provider: "provider-1",
  queries: ["Ada Lovelace"],
  query_count: 1,
  hit_count: 3,
  error: "",
  created_at: "2026-07-15T16:00:00Z",
  completed_at: "2026-07-15T16:01:00Z",
};

const photo: TargetPhoto = {
  id: "photo-1",
  case_id: "case-1",
  target_id: "target-1",
  source_id: null,
  filename: "portrait.png",
  content_type: "image/png",
  sha256: "abc123",
  size_bytes: 2048,
  created_at: "2026-07-14T12:00:00Z",
};

describe("buildTimelineEvents", () => {
  it("derives typed events from every existing record and preserves each record", () => {
    const events = buildTimelineEvents({
      auditEvents: [audit],
      sources: [source],
      searchRuns: [searchRun],
      targetPhotos: [photo],
    });

    expect(events.map((event) => event.type)).toEqual([
      "search_run",
      "audit",
      "source",
      "target_photo",
    ]);
    expect(events.map((event) => event.key)).toEqual([
      "search-run:run-1",
      "audit:7",
      "source:source-1",
      "target-photo:photo-1",
    ]);
    expect(events.find((event) => event.type === "audit")?.record).toBe(audit);
    expect(events.find((event) => event.type === "source")?.record).toBe(source);
    expect(events.find((event) => event.type === "search_run")?.record).toBe(searchRun);
    expect(events.find((event) => event.type === "target_photo")?.record).toBe(photo);
  });

  it("uses only the actual event timestamps from their source records", () => {
    const events = buildTimelineEvents({
      auditEvents: [audit],
      sources: [source],
      searchRuns: [searchRun],
      targetPhotos: [photo],
    });

    expect(events.map((event) => event.occurredAt)).toEqual([
      searchRun.created_at,
      audit.created_at,
      source.collected_at,
      photo.created_at,
    ]);
  });
});

describe("sortTimelineEventsDescending", () => {
  it("sorts newest first without mutating the input and leaves invalid dates last", () => {
    const validEvents = buildTimelineEvents({
      auditEvents: [audit],
      sources: [source],
      searchRuns: [],
      targetPhotos: [],
    });
    const invalidEvent: TimelineEvent = {
      key: "audit:8",
      type: "audit",
      occurredAt: "not-a-date",
      caseId: null,
      record: { ...audit, id: 8, case_id: null, created_at: "not-a-date" },
    };
    const input = [invalidEvent, ...validEvents];

    const sorted = sortTimelineEventsDescending(input);

    expect(sorted.map((event) => event.key)).toEqual(["audit:7", "source:source-1", "audit:8"]);
    expect(input[0]).toBe(invalidEvent);
  });
});

describe("filterTimelineEvents", () => {
  const events = buildTimelineEvents({
    auditEvents: [audit],
    sources: [source],
    searchRuns: [searchRun],
    targetPhotos: [photo],
  });

  it("keeps only selected types and maintains descending order", () => {
    const filtered = filterTimelineEvents(events, ["source", "search_run"]);

    expect(filtered.map((event) => event.type)).toEqual(["search_run", "source"]);
  });

  it("returns no events when no types are selected", () => {
    expect(filterTimelineEvents(events, new Set())).toEqual([]);
  });
});

describe("groupTimelineEventsByDay", () => {
  it("groups sorted events by their local calendar day", () => {
    const events = buildTimelineEvents({
      auditEvents: [audit],
      sources: [source],
      searchRuns: [searchRun],
      targetPhotos: [photo],
    });

    const groups = groupTimelineEventsByDay(events);

    expect(groups.map((group) => group.date)).toEqual(["2026-07-15", "2026-07-14"]);
    expect(groups[0].events.map((event) => event.type)).toEqual(["search_run", "audit", "source"]);
    expect(groups[1].events.map((event) => event.type)).toEqual(["target_photo"]);
  });

  it("uses the same local date that the UI renders for timezone-boundary events", () => {
    const timestamp = "2026-07-15T00:30:00Z";
    const localDate = new Date(timestamp);
    const expected = `${localDate.getFullYear()}-${String(localDate.getMonth() + 1).padStart(2, "0")}-${String(localDate.getDate()).padStart(2, "0")}`;
    const events = buildTimelineEvents({
      auditEvents: [{ ...audit, id: 99, created_at: timestamp }],
      sources: [],
      searchRuns: [],
      targetPhotos: [],
    });

    expect(groupTimelineEventsByDay(events)[0].date).toBe(expected);
  });
});

describe("serializeTimelineEvents", () => {
  it("exports real filtered records as readable JSON in descending order", () => {
    const events = buildTimelineEvents({
      auditEvents: [audit],
      sources: [source],
      searchRuns: [],
      targetPhotos: [],
    });
    const json = serializeTimelineEvents(filterTimelineEvents(events, ["source"]));
    const parsed = JSON.parse(json) as TimelineEvent[];

    expect(parsed).toHaveLength(1);
    expect(parsed[0].type).toBe("source");
    expect(parsed[0].record).toEqual(source);
    expect(json).toContain("\n  ");
  });
});
