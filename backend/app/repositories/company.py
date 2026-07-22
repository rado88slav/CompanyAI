"""Persistence operations for Company records."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import (
    Company,
    CompanyStatus,
)
from app.schemas.company import (
    CompanyCreate,
    CompanyUpdate,
)


class CompanyRepository:
    """Access Company records through a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, company_data: CompanyCreate) -> Company:
        """Create and flush a Company record."""

        company = Company(
            name=company_data.name,
            slug=company_data.slug,
        )

        self._session.add(company)
        self._session.flush()
        self._session.refresh(company)

        return company

    def get_by_id(self, company_id: UUID) -> Company | None:
        """Return a Company by UUID."""

        return self._session.get(Company, company_id)

    def get_by_slug(self, slug: str) -> Company | None:
        """Return a Company by its unique slug."""

        statement = select(Company).where(
            Company.slug == slug,
        )

        return self._session.scalar(statement)

    def list(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[Company]:
        """Return companies in deterministic creation order."""

        statement = (
            select(Company)
            .order_by(
                Company.created_at.asc(),
                Company.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )

        return list(
            self._session.scalars(statement).all()
        )

    def count(self) -> int:
        """Return the total number of companies."""

        statement = select(func.count()).select_from(Company)

        return int(
            self._session.scalar(statement) or 0
        )

    def update(
        self,
        company: Company,
        company_data: CompanyUpdate,
    ) -> Company:
        """Apply a partial update and flush the Company record."""

        update_fields = company_data.model_dump(
            exclude_unset=True,
        )

        for field_name, value in update_fields.items():
            setattr(company, field_name, value)

        self._session.flush()
        self._session.refresh(company)

        return company

    def set_active(
        self,
        company: Company,
        *,
        is_active: bool,
    ) -> Company:
        """Synchronize Company status and active flag."""

        company.is_active = is_active
        company.status = (
            CompanyStatus.ACTIVE.value
            if is_active
            else CompanyStatus.INACTIVE.value
        )

        self._session.flush()
        self._session.refresh(company)

        return company
