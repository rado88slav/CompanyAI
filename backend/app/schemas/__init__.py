"""Company AI API schemas."""

from app.schemas.authentication import (
    AdministratorCreate,
    AdministratorResponse,
    LoginRequest,
    TokenResponse,
)
from app.schemas.company import (
    CompanyCreate,
    CompanyListResponse,
    CompanyResponse,
    CompanyUpdate,
)
from app.schemas.company_setting import (
    CompanySettingListResponse,
    CompanySettingResponse,
    CompanySettingUpsert,
)

__all__ = [
    "AdministratorCreate",
    "AdministratorResponse",
    "CompanyCreate",
    "CompanyListResponse",
    "CompanyResponse",
    "CompanySettingListResponse",
    "CompanySettingResponse",
    "CompanySettingUpsert",
    "CompanyUpdate",
    "LoginRequest",
    "TokenResponse",
]
