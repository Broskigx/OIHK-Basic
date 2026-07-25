"""OSINT lookup and explicit graph-promotion services for OIHK Basic."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.services.osint_lookups import (
    LookupFinding,
    LookupResult,
    identify_kind,
    lookup_domain,
    lookup_email,
    lookup_ip,
)
from app.services.repository import ingest_source


@dataclass
class OsintReport:
    value: str
    kind: str
    findings: list[LookupFinding]
    errors: list[str]

    def summary(self) -> str:
        lines = [f"OSINT report for {self.value} ({self.kind})"]
        for finding in self.findings:
            lines.append(f"  [{finding.source}] {finding.type}: {finding.value} - {finding.detail}")
        if self.errors:
            lines.append("  Errors:")
            lines.extend(f"    - {error}" for error in self.errors)
        return "\n".join(lines)


async def run_lookup(value: str) -> OsintReport:
    """Run a supported public lookup without mutating the investigation."""
    value = value.strip().lower()
    kind = await identify_kind(value)
    if kind == "domain":
        result = await lookup_domain(value)
    elif kind == "ip":
        result = await lookup_ip(value)
    elif kind == "email":
        result = await lookup_email(value)
    else:
        result = LookupResult(value=value, kind="unknown", findings=[], errors=["Unknown value type"])
    return OsintReport(value=value, kind=kind, findings=result.findings, errors=result.errors)


def report_from_json(*, value: str, kind: str, findings: list[dict], errors: list[str]) -> OsintReport:
    """Rebuild a bounded report from persisted query history."""
    return OsintReport(
        value=value,
        kind=kind,
        findings=[
            LookupFinding(
                source=str(item.get("source", "unknown"))[:120],
                type=str(item.get("type", "observation"))[:120],
                value=str(item.get("value", ""))[:500],
                detail=str(item.get("detail", ""))[:2000],
            )
            for item in findings
        ],
        errors=[str(error)[:1000] for error in errors],
    )


async def ingest_report(
    session: AsyncSession,
    *,
    case_id: str,
    report: OsintReport,
) -> tuple[OsintReport, models.Source, list[models.Entity], list[models.Relationship]]:
    """Promote a stored lookup into a provenance-bearing source and graph."""
    body_lines = [f"OSINT Lookup: {report.value}", f"Type: {report.kind}", ""]
    for finding in report.findings:
        body_lines.extend(
            [
                f"Source: {finding.source}",
                f"  {finding.type}: {finding.value}",
                f"  Detail: {finding.detail}",
                "",
            ]
        )
    if report.errors:
        body_lines.append("Errors:")
        body_lines.extend(f"  - {error}" for error in report.errors)

    source, entities, relationships = await ingest_source(
        session,
        case_id=case_id,
        title=f"OSINT: {report.value}"[:240],
        kind=f"osint_{report.kind}",
        body="\n".join(body_lines),
        citation=f"osint:{report.value}",
        license="public-osint",
        reliability=0.7,
    )
    return report, source, entities, relationships
