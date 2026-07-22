"""HTTP endpoint for isolated company audit activity."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.authentication import require_current_administrator
from app.api.dependencies.company_authorization import require_company_activity_read
from app.schemas.audit_log import AuditLogListResponse, AuditLogResponse
from app.schemas.company_context import ActiveCompanyContext
from app.services.audit_log import AuditLogService, get_audit_log_service

router = APIRouter(
    prefix="/companies/{company_id}/activity",
    tags=["company-activity"],
    dependencies=[Depends(require_current_administrator)],
)


@router.get(
    "",
    response_model=AuditLogListResponse,
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
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditLogListResponse:
    """Return newest-first audit activity for the active company."""

    events, total = service.list_company_activity(
        company_id=company_id,
        limit=limit,
        offset=offset,
    )
    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(event) for event in events],
        total=total,
        limit=limit,
        offset=offset,
    )
