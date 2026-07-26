"""Safe first-run setup detection endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.administrator import Administrator
from app.models.company import Company
from app.schemas.first_run import FirstRunInitializeRequest, FirstRunInitializeResponse, FirstRunStatusResponse
from app.services.first_run import FirstRunAlreadyInitializedError, FirstRunConflictError, FirstRunService

router = APIRouter(prefix="/first-run", tags=["first-run"])


@router.get(
    "/status",
    response_model=FirstRunStatusResponse,
    summary="Check whether the local installation requires initial setup",
)
def get_first_run_status(
    session: Annotated[Session, Depends(get_db_session)],
) -> FirstRunStatusResponse:
    """Return non-secret initialization state for the dashboard."""

    administrator_count = int(
        session.scalar(select(func.count()).select_from(Administrator)) or 0
    )
    company_count = int(
        session.scalar(select(func.count()).select_from(Company)) or 0
    )
    initialized = administrator_count > 0
    return FirstRunStatusResponse(
        initialized=initialized,
        setup_required=not initialized,
        administrator_count=administrator_count,
        company_count=company_count,
        bootstrap_method="local_wizard",
    )


@router.post(
    "/initialize",
    response_model=FirstRunInitializeResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "The installation is already initialized.",
        },
    },
    summary="Initialize the local installation exactly once",
)
def initialize_first_run(
    payload: FirstRunInitializeRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> FirstRunInitializeResponse:
    """Create the first company and administrator while setup is open."""

    try:
        result = FirstRunService(session).initialize(payload)
    except (FirstRunAlreadyInitializedError, FirstRunConflictError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="First-run setup is already closed.",
        ) from exc

    return FirstRunInitializeResponse(
        initialized=True,
        company_id=result.company_id,
        company_slug=result.company_slug,
        administrator_id=result.administrator_id,
        administrator_email=result.administrator_email,
    )
