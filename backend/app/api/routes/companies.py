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
    CompanyUpdate,
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


def company_not_found_exception(
    exc: CompanyNotFoundError,
) -> HTTPException:
    """Create the standard Company not-found response."""

    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Company was not found.",
    )


def company_slug_conflict_exception(
    exc: CompanySlugConflictError,
) -> HTTPException:
    """Create the standard Company slug-conflict response."""

    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A company with this slug already exists.",
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
        raise company_slug_conflict_exception(exc) from exc

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
        raise company_not_found_exception(exc) from exc

    return CompanyResponse.model_validate(company)


@router.patch(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Update a company",
)
def update_company(
    company_id: UUID,
    company_data: CompanyUpdate,
    service: Annotated[
        CompanyService,
        Depends(get_company_service),
    ],
) -> CompanyResponse:
    """Partially update a Company Context."""

    try:
        company = service.update_company(
            company_id,
            company_data,
        )
    except CompanyNotFoundError as exc:
        raise company_not_found_exception(exc) from exc
    except CompanySlugConflictError as exc:
        raise company_slug_conflict_exception(exc) from exc

    return CompanyResponse.model_validate(company)


@router.post(
    "/{company_id}/activate",
    response_model=CompanyResponse,
    summary="Activate a company",
)
def activate_company(
    company_id: UUID,
    service: Annotated[
        CompanyService,
        Depends(get_company_service),
    ],
) -> CompanyResponse:
    """Activate a Company Context."""

    try:
        company = service.activate_company(company_id)
    except CompanyNotFoundError as exc:
        raise company_not_found_exception(exc) from exc

    return CompanyResponse.model_validate(company)


@router.post(
    "/{company_id}/deactivate",
    response_model=CompanyResponse,
    summary="Deactivate a company",
)
def deactivate_company(
    company_id: UUID,
    service: Annotated[
        CompanyService,
        Depends(get_company_service),
    ],
) -> CompanyResponse:
    """Deactivate a Company Context."""

    try:
        company = service.deactivate_company(company_id)
    except CompanyNotFoundError as exc:
        raise company_not_found_exception(exc) from exc

    return CompanyResponse.model_validate(company)
