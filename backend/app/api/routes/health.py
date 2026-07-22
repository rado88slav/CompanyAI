"""Backend health endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings, get_settings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Health endpoint response."""

    status: Literal["ok"]
    service: str
    environment: str
    version: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check backend health",
)
def read_health(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    """Return basic backend liveness information."""

    return HealthResponse(
        status="ok",
        service="backend",
        environment=settings.app_environment,
        version=settings.app_version,
    )
