import { useMemo, useState } from "react";
import type { AuditEvent, SearchRun, SourceRead, TargetPhoto } from "../../types";
import {
  buildTimelineEvents,
  filterTimelineEvents,
  groupTimelineEventsByDay,
  serializeTimelineEvents,
  TIMELINE_EVENT_TYPES,
  type TimelineEvent,
  type TimelineEventType,
} from "./timelineModel";
import "./timeline.css";

type TimelineViewProps = {
  auditEvents: readonly AuditEvent[];
  sources: readonly SourceRead[];
  searchRuns: readonly SearchRun[];
  targetPhotos: readonly TargetPhoto[];
  exportFileName?: string;
};

const TYPE_LABELS: Record<TimelineEventType, string> = {
  audit: "Audit",
  source: "Source",
  search_run: "Search run",
  target_photo: "Photo",
};

function formatEventDate(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(date);
}

function formatGroupDate(date: string | null): string {
  if (date === null) {
    return "Invalid date";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "full",
  }).format(new Date(`${date}T00:00:00`));
}

function formatByteCount(bytes: number): string {
  return `${new Intl.NumberFormat().format(bytes)} bytes`;
}

function EventContent({ event }: { event: TimelineEvent }) {
  switch (event.type) {
    case "audit":
      return (
        <>
          <h3 className="platform-timeline-card-title">{event.record.action}</h3>
          <dl className="platform-timeline-metadata">
            <div className="platform-timeline-metadata-row">
              <dt className="platform-timeline-metadata-label">Actor</dt>
              <dd className="platform-timeline-metadata-value">{event.record.actor}</dd>
            </div>
          </dl>
          {Object.keys(event.record.payload).length > 0 && (
            <pre className="platform-timeline-payload">
              {JSON.stringify(event.record.payload, null, 2)}
            </pre>
          )}
        </>
      );

    case "source":
      return (
        <>
          <h3 className="platform-timeline-card-title">{event.record.title}</h3>
          <dl className="platform-timeline-metadata">
            <div className="platform-timeline-metadata-row">
              <dt className="platform-timeline-metadata-label">Type</dt>
              <dd className="platform-timeline-metadata-value">{event.record.kind}</dd>
            </div>
            <div className="platform-timeline-metadata-row">
              <dt className="platform-timeline-metadata-label">Reliability</dt>
              <dd className="platform-timeline-metadata-value">{event.record.reliability}</dd>
            </div>
            {event.record.citation && (
              <div className="platform-timeline-metadata-row">
                <dt className="platform-timeline-metadata-label">Citation</dt>
                <dd className="platform-timeline-metadata-value">{event.record.citation}</dd>
              </div>
            )}
          </dl>
        </>
      );

    case "search_run":
      return (
        <>
          <h3 className="platform-timeline-card-title">{event.record.provider}</h3>
          <dl className="platform-timeline-metadata">
            <div className="platform-timeline-metadata-row">
              <dt className="platform-timeline-metadata-label">Status</dt>
              <dd className="platform-timeline-metadata-value">{event.record.status}</dd>
            </div>
            <div className="platform-timeline-metadata-row">
              <dt className="platform-timeline-metadata-label">Queries</dt>
              <dd className="platform-timeline-metadata-value">{event.record.query_count}</dd>
            </div>
            <div className="platform-timeline-metadata-row">
              <dt className="platform-timeline-metadata-label">Results</dt>
              <dd className="platform-timeline-metadata-value">{event.record.hit_count}</dd>
            </div>
            {event.record.completed_at && (
              <div className="platform-timeline-metadata-row">
                <dt className="platform-timeline-metadata-label">Completed</dt>
                <dd className="platform-timeline-metadata-value">
                  <time dateTime={event.record.completed_at}>{formatEventDate(event.record.completed_at)}</time>
                </dd>
              </div>
            )}
            {event.record.error && (
              <div className="platform-timeline-metadata-row">
                <dt className="platform-timeline-metadata-label">Error</dt>
                <dd className="platform-timeline-metadata-value platform-timeline-error">
                  {event.record.error}
                </dd>
              </div>
            )}
          </dl>
          {event.record.queries.length > 0 && (
            <ul className="platform-timeline-query-list">
              {event.record.queries.map((query, index) => (
                <li className="platform-timeline-query" key={`${event.key}:query:${index}`}>
                  {query}
                </li>
              ))}
            </ul>
          )}
        </>
      );

    case "target_photo":
      return (
        <>
          <h3 className="platform-timeline-card-title">{event.record.filename}</h3>
          <dl className="platform-timeline-metadata">
            <div className="platform-timeline-metadata-row">
              <dt className="platform-timeline-metadata-label">Format</dt>
              <dd className="platform-timeline-metadata-value">{event.record.content_type}</dd>
            </div>
            <div className="platform-timeline-metadata-row">
              <dt className="platform-timeline-metadata-label">Size</dt>
              <dd className="platform-timeline-metadata-value">{formatByteCount(event.record.size_bytes)}</dd>
            </div>
            <div className="platform-timeline-metadata-row">
              <dt className="platform-timeline-metadata-label">SHA-256</dt>
              <dd className="platform-timeline-metadata-value platform-timeline-hash">
                {event.record.sha256}
              </dd>
            </div>
          </dl>
        </>
      );
  }
}

function downloadJson(contents: string, fileName: string): void {
  const url = URL.createObjectURL(new Blob([contents], { type: "application/json;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

export function TimelineView({
  auditEvents,
  sources,
  searchRuns,
  targetPhotos,
  exportFileName = "timeline.json",
}: TimelineViewProps) {
  const [selectedTypes, setSelectedTypes] = useState<Set<TimelineEventType>>(
    () => new Set(TIMELINE_EVENT_TYPES),
  );
  const events = useMemo(
    () => buildTimelineEvents({ auditEvents, sources, searchRuns, targetPhotos }),
    [auditEvents, sources, searchRuns, targetPhotos],
  );
  const visibleEvents = useMemo(
    () => filterTimelineEvents(events, selectedTypes),
    [events, selectedTypes],
  );
  const groups = useMemo(() => groupTimelineEventsByDay(visibleEvents), [visibleEvents]);

  function toggleType(type: TimelineEventType): void {
    setSelectedTypes((current) => {
      const next = new Set(current);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  }

  return (
    <section className="platform-timeline" aria-labelledby="platform-timeline-title">
      <header className="platform-timeline-header">
        <div className="platform-timeline-heading">
          <h2 className="platform-timeline-title" id="platform-timeline-title">
            Timeline
          </h2>
          <span className="platform-timeline-count" aria-live="polite">
            {visibleEvents.length} of {events.length} events
          </span>
        </div>
        <button
          className="platform-timeline-export"
          type="button"
          disabled={visibleEvents.length === 0}
          onClick={() => downloadJson(serializeTimelineEvents(visibleEvents), exportFileName)}
        >
          Export JSON
        </button>
      </header>

      <div className="platform-timeline-filters" aria-label="Filter events by type">
        {TIMELINE_EVENT_TYPES.map((type) => (
          <button
            className="platform-timeline-filter"
            data-active={selectedTypes.has(type)}
            type="button"
            aria-pressed={selectedTypes.has(type)}
            key={type}
            onClick={() => toggleType(type)}
          >
            {TYPE_LABELS[type]}
          </button>
        ))}
      </div>

      {groups.length === 0 ? (
        <p className="platform-timeline-empty">No events match the selected filters.</p>
      ) : (
        <div className="platform-timeline-groups">
          {groups.map((group) => (
            <section className="platform-timeline-group" key={group.date ?? "invalid-date"}>
              <h3 className="platform-timeline-day">{formatGroupDate(group.date)}</h3>
              <ol className="platform-timeline-list">
                {group.events.map((event) => (
                  <li className="platform-timeline-item" data-type={event.type} key={event.key}>
                    <span className="platform-timeline-marker" aria-hidden="true" />
                    <article className="platform-timeline-card">
                      <div className="platform-timeline-card-header">
                        <span className="platform-timeline-type">{TYPE_LABELS[event.type]}</span>
                        <time className="platform-timeline-time" dateTime={event.occurredAt}>
                          {formatEventDate(event.occurredAt)}
                        </time>
                      </div>
                      <EventContent event={event} />
                      {event.caseId && (
                        <small className="platform-timeline-case">Case {event.caseId}</small>
                      )}
                    </article>
                  </li>
                ))}
              </ol>
            </section>
          ))}
        </div>
      )}
    </section>
  );
}
