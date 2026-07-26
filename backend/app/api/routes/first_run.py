"""Safe first-run setup detection endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.administrator import Administrator
from app.models.company import Company
from app.schemas.first_run import FirstRunStatusResponse

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
        bootstrap_method="local_cli",
    )
