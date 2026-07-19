"""OSINT service for OIHK Basic."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.services.osint_lookups import identify_kind, lookup_domain, lookup_email, lookup_ip, LookupResult
from app.services.repository import ingest_source


@dataclass
class OsintReport:
    value: str
    kind: str
    findings: list
    errors: list[str]

    def summary(self) -> str:
        lines = [f"OSINT Report for {self.value} ({self.kind})"]
        for f in self.findings:
            lines.append(f"  [{f.source}] {f.type}: {f.value} — {f.detail}")
        if self.errors:
            lines.append("  Errors:")
            for e in self.errors:
                lines.append(f"    - {e}")
        return "\n".join(lines)


async def run_and_ingest(
    session: AsyncSession,
    *,
    case_id: str,
    value: str,
    actor: str = "analyst",
) -> tuple[OsintReport, models.Source, list[models.Entity], list[models.Relationship]]:
    kind = await identify_kind(value)

    if kind == "domain":
        result = await lookup_domain(value)
    elif kind == "ip":
        result = await lookup_ip(value)
    elif kind == "email":
        result = await lookup_email(value)
    else:
        result = LookupResult(value=value, kind="unknown", findings=[], errors=["Unknown value type"])

    report = OsintReport(value=value, kind=kind, findings=result.findings, errors=result.errors)

    body_lines = [f"OSINT Lookup: {value}", f"Type: {kind}", ""]
    for f in result.findings:
        body_lines.append(f"Source: {f.source}")
        body_lines.append(f"  {f.type}: {f.value}")
        body_lines.append(f"  Detail: {f.detail}")
        body_lines.append("")
    if result.errors:
        body_lines.append("Errors:")
        for e in result.errors:
            body_lines.append(f"  - {e}")

    source, entities, relationships = await ingest_source(
        session,
        case_id=case_id,
        title=f"OSINT: {value}"[:240],
        kind=f"osint_{kind}",
        body="\n".join(body_lines),
        citation=f"osint:{value}",
        license="public-osint",
        reliability=0.7,
    )

    return report, source, entities, relationships
