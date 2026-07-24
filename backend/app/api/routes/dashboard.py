"""Authenticated read-only company dashboard endpoint."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies.authentication import require_current_administrator
from app.api.dependencies.company_authorization import (
    require_approvals_read,
    require_company_activity_read,
    require_provider_executions_read,
    require_providers_read,
)
from app.schemas.company_context import ActiveCompanyContext
from app.schemas.dashboard import DashboardSummaryResponse
from app.services.dashboard import DashboardService, get_dashboard_service

router = APIRouter(
    prefix="/companies/{company_id}/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_current_administrator)],
)


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    summary="Show company dashboard summary",
)
def get_dashboard_summary(
    company_id: UUID,
    _activity_context: Annotated[
        ActiveCompanyContext,
        Depends(require_company_activity_read),
    ],
    _provider_context: Annotated[
        ActiveCompanyContext,
        Depends(require_providers_read),
    ],
    _approval_context: Annotated[
        ActiveCompanyContext,
        Depends(require_approvals_read),
    ],
    _execution_context: Annotated[
        ActiveCompanyContext,
        Depends(require_provider_executions_read),
    ],
    service: Annotated[
        DashboardService,
        Depends(get_dashboard_service),
    ],
) -> DashboardSummaryResponse:
    """Return a safe company-scoped operational overview."""

    return service.get_summary(company_id=company_id)
