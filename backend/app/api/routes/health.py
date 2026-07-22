"""Backend health and readiness endpoints."""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Basic backend liveness response."""

    status: Literal["ok"]
    service: str
    environment: str
    version: str


class ReadinessResponse(BaseModel):
    """Backend and database readiness response."""

    status: Literal["ok"]
    service: str
    database: Literal["reachable"]


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


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "PostgreSQL is unavailable.",
        },
    },
    summary="Check backend and database readiness",
)
def read_readiness(
    session: Annotated[Session, Depends(get_db_session)],
) -> ReadinessResponse:
    """Verify that the backend can execute a PostgreSQL query."""

    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.exception("PostgreSQL readiness check failed.")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from exc

    return ReadinessResponse(
        status="ok",
        service="backend",
        database="reachable",
    )
