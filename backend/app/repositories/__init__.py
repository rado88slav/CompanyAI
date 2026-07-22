"""Database repository package."""

from app.repositories.administrator import (
    AdministratorRepository,
)
from app.repositories.company import CompanyRepository
from app.repositories.company_setting import (
    CompanySettingRepository,
)

__all__ = [
    "AdministratorRepository",
    "CompanyRepository",
    "CompanySettingRepository",
]
