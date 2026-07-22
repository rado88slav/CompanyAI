"""Application service for the Company domain."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.audit_log import AuditAction
from app.models.company import Company
from app.repositories.company import CompanyRepository
from app.schemas.company import (
    CompanyCreate,
    CompanyUpdate,
)
from app.repositories.audit_log import AuditLogRepository
from app.services.audit_log import AuditLogService


class CompanyNotFoundError(Exception):
    """Raised when a requested company does not exist."""


class CompanySlugConflictError(Exception):
    """Raised when a company slug is already in use."""


class CompanyService:
    """Coordinate Company domain operations."""

    def __init__(
        self,
        repository: CompanyRepository,
        audit_service: AuditLogService,
        session: Session,
    ) -> None:
        self._repository = repository
        self._audit_service = audit_service
        self._session = session

    def create_company(
        self,
        company_data: CompanyCreate,
        *,
        actor_administrator_id: UUID,
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
        except IntegrityError as exc:
            self._session.rollback()

            raise CompanySlugConflictError(
                f"Company slug already exists: {company_data.slug}"
            ) from exc
        except Exception:
            self._session.rollback()
            raise

        try:
            self._audit_service.append_company_event(
                company_id=company.id,
                actor_administrator_id=actor_administrator_id,
                action=AuditAction.COMPANY_CREATED.value,
                resource_type="company",
                resource_id=company.id,
                details={"name": company.name, "slug": company.slug},
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

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

    def update_company(
        self,
        company_id: UUID,
        company_data: CompanyUpdate,
        *,
        actor_administrator_id: UUID,
    ) -> Company:
        """Partially update an existing company."""

        company = self.get_company(company_id)

        if (
            company_data.slug is not None
            and company_data.slug != company.slug
        ):
            existing_company = self._repository.get_by_slug(
                company_data.slug
            )

            if (
                existing_company is not None
                and existing_company.id != company.id
            ):
                raise CompanySlugConflictError(
                    f"Company slug already exists: {company_data.slug}"
                )

        previous_values = {
            field_name: getattr(company, field_name)
            for field_name in company_data.model_fields_set
        }

        try:
            updated_company = self._repository.update(
                company,
                company_data,
            )
        except IntegrityError as exc:
            self._session.rollback()

            raise CompanySlugConflictError(
                "Company slug already exists."
            ) from exc
        except Exception:
            self._session.rollback()
            raise

        changes = {
            field_name: {
                "from": previous_values[field_name],
                "to": getattr(updated_company, field_name),
            }
            for field_name in company_data.model_fields_set
            if previous_values[field_name]
            != getattr(updated_company, field_name)
        }

        try:
            self._audit_service.append_company_event(
                company_id=updated_company.id,
                actor_administrator_id=actor_administrator_id,
                action=AuditAction.COMPANY_UPDATED.value,
                resource_type="company",
                resource_id=updated_company.id,
                details={"changed": bool(changes), "changes": changes},
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        return updated_company

    def activate_company(
        self,
        company_id: UUID,
        *,
        actor_administrator_id: UUID,
    ) -> Company:
        """Activate a company and synchronize its status."""

        company = self.get_company(company_id)
        previous_status = company.status

        try:
            activated_company = self._repository.set_active(
                company,
                is_active=True,
            )
            self._audit_service.append_company_event(
                company_id=activated_company.id,
                actor_administrator_id=actor_administrator_id,
                action=AuditAction.COMPANY_ACTIVATED.value,
                resource_type="company",
                resource_id=activated_company.id,
                details={
                    "previous_status": previous_status,
                    "new_status": activated_company.status,
                    "changed": previous_status != activated_company.status,
                },
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        return activated_company

    def deactivate_company(
        self,
        company_id: UUID,
        *,
        actor_administrator_id: UUID,
    ) -> Company:
        """Deactivate a company and synchronize its status."""

        company = self.get_company(company_id)
        previous_status = company.status

        try:
            deactivated_company = self._repository.set_active(
                company,
                is_active=False,
            )
            self._audit_service.append_company_event(
                company_id=deactivated_company.id,
                actor_administrator_id=actor_administrator_id,
                action=AuditAction.COMPANY_DEACTIVATED.value,
                resource_type="company",
                resource_id=deactivated_company.id,
                details={
                    "previous_status": previous_status,
                    "new_status": deactivated_company.status,
                    "changed": previous_status != deactivated_company.status,
                },
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        return deactivated_company


def get_company_service(
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
) -> CompanyService:
    """Create a request-scoped Company service."""

    return CompanyService(
        repository=CompanyRepository(session),
        audit_service=AuditLogService(AuditLogRepository(session)),
        session=session,
    )
