"""Company AI database models.

Every SQLAlchemy model must be imported here so Alembic can discover its
metadata during automatic migration generation.
"""

from app.models.company import Company, CompanyStatus

__all__ = [
    "Company",
    "CompanyStatus",
]
