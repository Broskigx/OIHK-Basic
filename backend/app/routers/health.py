from fastapi import APIRouter

from app.schemas import HealthRead

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthRead)
async def health() -> HealthRead:
    return HealthRead(status="ok", service="oihk-basic-api", version="0.1.0")
