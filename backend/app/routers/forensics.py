"""Forensics router for OIHK Basic."""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_case_access
from app.database import get_session
from app.schemas import ForensicFindingRead, ForensicReportRead
from app.services.forensic_evidence import read_forensic_upload, store_forensic_evidence

router = APIRouter(prefix="/forensics", tags=["forensics"])


@router.post("/analyze", response_model=ForensicReportRead, status_code=201)
async def analyze_upload(
    case_id: str = Form(...),
    file: UploadFile = File(...),
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ForensicReportRead:
    """Analyze an uploaded media file for hidden data and file it as sealed evidence."""
    await require_case_access(session, case_id, current)

    data = await read_forensic_upload(file)
    stored = await store_forensic_evidence(
        session,
        case_id=case_id,
        filename=file.filename or "upload",
        content_type=file.content_type or "",
        data=data,
        actor=current.username,
        organization_id=current.organization_id,
    )
    await session.commit()

    return ForensicReportRead(
        filename=stored.report.filename,
        size_bytes=stored.report.size_bytes,
        sha256=stored.report.sha256,
        detected_type=stored.report.detected_type,
        detected_label=stored.report.detected_label,
        claimed_type=stored.report.claimed_type,
        type_mismatch=stored.report.type_mismatch,
        entropy=stored.report.entropy,
        max_window_entropy=stored.report.max_window_entropy,
        trailing_bytes=stored.report.trailing_bytes,
        embedded_signatures=stored.report.embedded_signatures,
        lsb=stored.report.lsb,
        media_metadata=stored.report.media_metadata,
        suspicion_score=stored.report.suspicion_score,
        verdict=stored.report.verdict,
        findings=[
            ForensicFindingRead(severity=finding.severity, code=finding.code, detail=finding.detail)
            for finding in stored.report.findings
        ],
        source_id=stored.source.id,
    )
