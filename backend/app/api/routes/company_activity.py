"""HTTP endpoint for isolated company audit activity."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.authentication import require_current_administrator
from app.api.dependencies.company_authorization import require_company_activity_read
from app.schemas.activity import ActivityEventListResponse
from app.schemas.company_context import ActiveCompanyContext
from app.services.audit_log import AuditLogService, get_audit_log_service

router = APIRouter(
    prefix="/companies/{company_id}/activity",
    tags=["company-activity"],
    dependencies=[Depends(require_current_administrator)],
)


@router.get(
    "",
    response_model=ActivityEventListResponse,
    summary="List company activity",
)
def list_company_activity(
    company_id: UUID,
    _context: Annotated[
        ActiveCompanyContext,
        Depends(require_company_activity_read),
    ],
    service: Annotated[
        AuditLogService,
        Depends(get_audit_log_service),
    ],
    event_type: str | None = Query(None, max_length=50),
    source: str | None = Query(None, max_length=50),
    severity: str | None = Query(None, pattern="^(info|warning|error)$"),
    actor: str | None = Query(None, pattern="^(administrator|agent|system)$"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ActivityEventListResponse:
    """Return newest-first normalized activity for the active company."""

    events, total = service.list_company_activity(
        company_id=company_id,
        limit=limit,
        offset=offset,
        event_type=event_type,
        source=source,
        severity=severity,
        actor=actor,
        date_from=date_from,
        date_to=date_to,
    )
    return ActivityEventListResponse(
        items=events,
        total=total,
        limit=limit,
        offset=offset,
    )
