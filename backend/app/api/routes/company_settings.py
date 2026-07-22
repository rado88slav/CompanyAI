"""HTTP endpoints for company-owned settings."""

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    status,
)

from app.schemas.company_setting import (
    CompanySettingListResponse,
    CompanySettingResponse,
    CompanySettingUpsert,
)
from app.services.company import CompanyNotFoundError
from app.services.company_setting import (
    CompanySettingNotFoundError,
    CompanySettingService,
    get_company_setting_service,
)

router = APIRouter(
    prefix="/companies/{company_id}/settings",
    tags=["company-settings"],
)

SettingCategory = Annotated[
    str,
    Path(
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$",
    ),
]

SettingKey = Annotated[
    str,
    Path(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$",
    ),
]


def company_not_found_exception(
    exc: CompanyNotFoundError,
) -> HTTPException:
    """Create the standard Company not-found response."""

    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Company was not found.",
    )


def setting_not_found_exception(
    exc: CompanySettingNotFoundError,
) -> HTTPException:
    """Create the standard setting not-found response."""

    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Company setting was not found.",
    )


@router.put(
    "/{category}/{key}",
    response_model=CompanySettingResponse,
    summary="Create or replace a company setting",
)
def upsert_company_setting(
    company_id: UUID,
    category: SettingCategory,
    key: SettingKey,
    setting_data: CompanySettingUpsert,
    service: Annotated[
        CompanySettingService,
        Depends(get_company_setting_service),
    ],
) -> CompanySettingResponse:
    """Create a setting or replace its current value."""

    try:
        setting = service.upsert_setting(
            company_id=company_id,
            category=category,
            key=key,
            setting_data=setting_data,
        )
    except CompanyNotFoundError as exc:
        raise company_not_found_exception(exc) from exc

    return CompanySettingResponse.model_validate(setting)


@router.get(
    "",
    response_model=CompanySettingListResponse,
    summary="List company settings",
)
def list_company_settings(
    company_id: UUID,
    service: Annotated[
        CompanySettingService,
        Depends(get_company_setting_service),
    ],
    category: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=50,
            pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$",
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> CompanySettingListResponse:
    """Return a paginated collection of company settings."""

    try:
        settings, total = service.list_settings(
            company_id=company_id,
            category=category,
            limit=limit,
            offset=offset,
        )
    except CompanyNotFoundError as exc:
        raise company_not_found_exception(exc) from exc

    return CompanySettingListResponse(
        items=[
            CompanySettingResponse.model_validate(setting)
            for setting in settings
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{category}/{key}",
    response_model=CompanySettingResponse,
    summary="Get a company setting",
)
def get_company_setting(
    company_id: UUID,
    category: SettingCategory,
    key: SettingKey,
    service: Annotated[
        CompanySettingService,
        Depends(get_company_setting_service),
    ],
) -> CompanySettingResponse:
    """Return one company setting."""

    try:
        setting = service.get_setting(
            company_id=company_id,
            category=category,
            key=key,
        )
    except CompanyNotFoundError as exc:
        raise company_not_found_exception(exc) from exc
    except CompanySettingNotFoundError as exc:
        raise setting_not_found_exception(exc) from exc

    return CompanySettingResponse.model_validate(setting)


@router.delete(
    "/{category}/{key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a company setting",
)
def delete_company_setting(
    company_id: UUID,
    category: SettingCategory,
    key: SettingKey,
    service: Annotated[
        CompanySettingService,
        Depends(get_company_setting_service),
    ],
) -> Response:
    """Delete one company setting."""

    try:
        service.delete_setting(
            company_id=company_id,
            category=category,
            key=key,
        )
    except CompanyNotFoundError as exc:
        raise company_not_found_exception(exc) from exc
    except CompanySettingNotFoundError as exc:
        raise setting_not_found_exception(exc) from exc

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
