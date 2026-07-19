"""Timeline builder for OIHK Basic."""

from app.forensic.types import TimelineEvent


def build_timeline(data: bytes, filename: str, sha256: str) -> list[TimelineEvent]:
    """Build a timeline of events from file analysis."""
    events: list[TimelineEvent] = []
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    events.append(TimelineEvent(
        event_id="analysis_start",
        source_id=None,
        title=f"Analysis started: {filename}",
        event_type="analysis",
        timestamp=now.isoformat(),
        detail=f"File analysis initiated for {filename} ({len(data)} bytes)",
        metadata={"sha256": sha256, "size": len(data)},
    ))

    return events
