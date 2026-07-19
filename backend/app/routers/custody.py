"""Custody router for OIHK Basic."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_case_access
from app.database import get_session
from app.schemas import CustodyReportRead, SealStatusRead
from app.services.custody import verify_case_custody

router = APIRouter(prefix="/custody", tags=["custody"])


@router.get("/{case_id}", response_model=CustodyReportRead)
async def get_custody_report(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CustodyReportRead:
    """Verify the tamper-evident chain of custody for a case's evidence."""
    await require_case_access(session, case_id, current)

    report = await verify_case_custody(session, case_id)
    return CustodyReportRead(
        case_id=report.case_id,
        intact=report.intact,
        sealed_count=report.sealed_count,
        first_broken_sequence=report.first_broken_sequence,
        entries=[
            SealStatusRead(
                sequence=entry.sequence,
                source_id=entry.source_id,
                source_title=entry.source_title,
                sealed_at_iso=entry.sealed_at_iso,
                content_sha256=entry.content_sha256,
                seal_hash=entry.seal_hash,
                content_ok=entry.content_ok,
                seal_ok=entry.seal_ok,
                chain_ok=entry.chain_ok,
                signature_ok=entry.signature_ok,
                ok=entry.ok,
            )
            for entry in report.entries
        ],
    )
