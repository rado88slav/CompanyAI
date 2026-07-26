"""HTTP endpoint for resolving active company context."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.authentication import require_current_administrator
from app.api.dependencies.company_context import require_active_company_context
from app.models.administrator import Administrator
from app.schemas.company import CompanyResponse
from app.schemas.company_context import (
    ActiveCompanyContext,
    ActiveCompanyContextResponse,
    AvailableCompanyContext,
    AvailableCompanyContextListResponse,
)
from app.services.company import CompanyService, get_company_service

router = APIRouter(tags=["company-context"])


@router.get(
    "/company-context",
    response_model=ActiveCompanyContextResponse,
    summary="Resolve the active company context",
)
def get_active_company_context(
    context: Annotated[
        ActiveCompanyContext,
        Depends(require_active_company_context),
    ],
) -> ActiveCompanyContextResponse:
    """Return the company selected for the current request."""

    return ActiveCompanyContextResponse(
        company=CompanyResponse.model_validate(context.company),
        membership_role=(context.membership.role if context.membership else None),
        is_platform_superuser=context.is_platform_superuser,
    )


@router.get(
    "/company-context/available-companies",
    response_model=AvailableCompanyContextListResponse,
    summary="List companies available to the authenticated administrator",
)
def list_available_company_contexts(
    administrator: Annotated[
        Administrator,
        Depends(require_current_administrator),
    ],
    service: Annotated[
        CompanyService,
        Depends(get_company_service),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AvailableCompanyContextListResponse:
    """Return active company contexts the current administrator may choose."""

    items, total = service.list_available_company_contexts(
        administrator_id=administrator.id,
        is_superuser=administrator.is_superuser,
        limit=limit,
        offset=offset,
    )

    return AvailableCompanyContextListResponse(
        items=[
            AvailableCompanyContext(
                company=CompanyResponse.model_validate(company),
                membership_role=(membership.role if membership else None),
                is_platform_superuser=administrator.is_superuser,
            )
            for company, membership in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
