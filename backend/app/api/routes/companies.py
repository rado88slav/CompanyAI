"""HTTP endpoints for Company Context management."""

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from app.schemas.company import (
    CompanyCreate,
    CompanyListResponse,
    CompanyResponse,
)
from app.services.company import (
    CompanyNotFoundError,
    CompanyService,
    CompanySlugConflictError,
    get_company_service,
)

router = APIRouter(
    prefix="/companies",
    tags=["companies"],
)


@router.post(
    "",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a company",
)
def create_company(
    company_data: CompanyCreate,
    service: Annotated[
        CompanyService,
        Depends(get_company_service),
    ],
) -> CompanyResponse:
    """Create a new Company Context."""

    try:
        company = service.create_company(company_data)
    except CompanySlugConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A company with this slug already exists.",
        ) from exc

    return CompanyResponse.model_validate(company)


@router.get(
    "",
    response_model=CompanyListResponse,
    summary="List companies",
)
def list_companies(
    service: Annotated[
        CompanyService,
        Depends(get_company_service),
    ],
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> CompanyListResponse:
    """Return a paginated collection of companies."""

    companies, total = service.list_companies(
        limit=limit,
        offset=offset,
    )

    return CompanyListResponse(
        items=[
            CompanyResponse.model_validate(company)
            for company in companies
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Get a company",
)
def get_company(
    company_id: UUID,
    service: Annotated[
        CompanyService,
        Depends(get_company_service),
    ],
) -> CompanyResponse:
    """Return one Company Context by UUID."""

    try:
        company = service.get_company(company_id)
    except CompanyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company was not found.",
        ) from exc

    return CompanyResponse.model_validate(company)
