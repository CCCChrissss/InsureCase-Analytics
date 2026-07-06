from __future__ import annotations

from fastapi import APIRouter

from backend.app.database import DEFAULT_DB_PATH
from backend.app.schemas import HealthResponse


router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", database_ready=DEFAULT_DB_PATH.is_file())
