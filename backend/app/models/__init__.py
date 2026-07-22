"""Company AI database models.

Every SQLAlchemy model must be imported here so Alembic can discover its
metadata during automatic migration generation.
"""

from app.models.company import Company, CompanyStatus
from app.models.company_setting import CompanySetting

__all__ = [
    "Company",
    "CompanySetting",
    "CompanyStatus",
]
