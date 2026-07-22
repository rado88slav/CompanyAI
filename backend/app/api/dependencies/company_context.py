"""FastAPI dependencies for stateless active company context."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Path, status

from app.api.dependencies.authentication import require_current_administrator
from app.models.administrator import Administrator
from app.models.company import CompanyStatus
from app.schemas.company_context import ActiveCompanyContext
from app.services.company import (
    CompanyNotFoundError,
    CompanyService,
    get_company_service,
)


def invalid_company_header_exception() -> HTTPException:
    """Create the standard invalid company-header response."""

    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="X-Company-ID header must contain a valid company UUID.",
    )


def require_active_company_context(
    administrator: Annotated[
        Administrator,
        Depends(require_current_administrator),
    ],
    service: Annotated[
        CompanyService,
        Depends(get_company_service),
    ],
    company_header: Annotated[
        str | None,
        Header(alias="X-Company-ID"),
    ] = None,
) -> ActiveCompanyContext:
    """Resolve an active company selected by an authenticated superuser."""

    if company_header is None or not company_header.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Company-ID header is required.",
        )

    try:
        company_id = UUID(company_header.strip())
    except (ValueError, AttributeError) as exc:
        raise invalid_company_header_exception() from exc

    if not administrator.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access is required to select a company context.",
        )

    try:
        company = service.get_company(company_id)
    except CompanyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company was not found.",
        ) from exc

    if not company.is_active or company.status != CompanyStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inactive company cannot be selected as active context.",
        )

    return ActiveCompanyContext(
        administrator=administrator,
        company=company,
    )


def require_matching_active_company(
    company_id: Annotated[UUID, Path()],
    context: Annotated[
        ActiveCompanyContext,
        Depends(require_active_company_context),
    ],
) -> ActiveCompanyContext:
    """Require a company path UUID to match the selected request context."""

    if company_id != context.company.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="URL company_id must match the X-Company-ID company context.",
        )

    return context
