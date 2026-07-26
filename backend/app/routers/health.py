from fastapi import APIRouter

from app.schemas import HealthRead
from app.version import PRODUCT_VERSION

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthRead)
async def health() -> HealthRead:
    return HealthRead(status="ok", service="oihk-basic-api", version=PRODUCT_VERSION)
