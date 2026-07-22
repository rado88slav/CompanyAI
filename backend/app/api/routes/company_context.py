"""HTTP endpoint for resolving active company context."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies.company_context import require_active_company_context
from app.schemas.company import CompanyResponse
from app.schemas.company_context import (
    ActiveCompanyContext,
    ActiveCompanyContextResponse,
)

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
    )
