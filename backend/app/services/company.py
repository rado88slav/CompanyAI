"""Application service for the Company domain."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.company import Company
from app.repositories.company import CompanyRepository
from app.schemas.company import CompanyCreate


class CompanyNotFoundError(Exception):
    """Raised when a requested company does not exist."""


class CompanySlugConflictError(Exception):
    """Raised when a company slug is already in use."""


class CompanyService:
    """Coordinate Company domain operations."""

    def __init__(
        self,
        repository: CompanyRepository,
        session: Session,
    ) -> None:
        self._repository = repository
        self._session = session

    def create_company(
        self,
        company_data: CompanyCreate,
    ) -> Company:
        """Create a new company with a unique slug."""

        existing_company = self._repository.get_by_slug(
            company_data.slug
        )

        if existing_company is not None:
            raise CompanySlugConflictError(
                f"Company slug already exists: {company_data.slug}"
            )

        try:
            company = self._repository.create(company_data)
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()

            raise CompanySlugConflictError(
                f"Company slug already exists: {company_data.slug}"
            ) from exc

        return company

    def get_company(self, company_id: UUID) -> Company:
        """Return one company or raise a domain error."""

        company = self._repository.get_by_id(company_id)

        if company is None:
            raise CompanyNotFoundError(
                f"Company not found: {company_id}"
            )

        return company

    def list_companies(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Company], int]:
        """Return a page of companies and the total count."""

        companies = self._repository.list(
            limit=limit,
            offset=offset,
        )

        total = self._repository.count()

        return companies, total


def get_company_service(
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
) -> CompanyService:
    """Create a request-scoped Company service."""

    return CompanyService(
        repository=CompanyRepository(session),
        session=session,
    )
