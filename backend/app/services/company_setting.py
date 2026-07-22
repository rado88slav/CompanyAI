"""Application service for company-owned settings."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.company import Company
from app.models.company_setting import CompanySetting
from app.repositories.company import CompanyRepository
from app.repositories.company_setting import (
    CompanySettingRepository,
)
from app.schemas.company_setting import CompanySettingUpsert
from app.services.company import CompanyNotFoundError


class CompanySettingNotFoundError(Exception):
    """Raised when a requested company setting does not exist."""


class CompanySettingService:
    """Coordinate company-owned setting operations."""

    def __init__(
        self,
        setting_repository: CompanySettingRepository,
        company_repository: CompanyRepository,
        session: Session,
    ) -> None:
        self._setting_repository = setting_repository
        self._company_repository = company_repository
        self._session = session

    def _get_company(self, company_id: UUID) -> Company:
        """Return the owning company or raise a domain error."""

        company = self._company_repository.get_by_id(
            company_id
        )

        if company is None:
            raise CompanyNotFoundError(
                f"Company not found: {company_id}"
            )

        return company

    def upsert_setting(
        self,
        *,
        company_id: UUID,
        category: str,
        key: str,
        setting_data: CompanySettingUpsert,
    ) -> CompanySetting:
        """Create or replace one company setting."""

        self._get_company(company_id)

        setting = self._setting_repository.get(
            company_id=company_id,
            category=category,
            key=key,
        )

        try:
            if setting is None:
                setting = self._setting_repository.create(
                    company_id=company_id,
                    category=category,
                    key=key,
                    setting_data=setting_data,
                )
            else:
                setting = self._setting_repository.replace_value(
                    setting,
                    setting_data,
                )

            self._session.commit()
        except IntegrityError:
            self._session.rollback()

            setting = self._setting_repository.get(
                company_id=company_id,
                category=category,
                key=key,
            )

            if setting is None:
                raise

            setting = self._setting_repository.replace_value(
                setting,
                setting_data,
            )

            self._session.commit()

        return setting

    def get_setting(
        self,
        *,
        company_id: UUID,
        category: str,
        key: str,
    ) -> CompanySetting:
        """Return one setting or raise a domain error."""

        self._get_company(company_id)

        setting = self._setting_repository.get(
            company_id=company_id,
            category=category,
            key=key,
        )

        if setting is None:
            raise CompanySettingNotFoundError(
                "Company setting was not found."
            )

        return setting

    def list_settings(
        self,
        *,
        company_id: UUID,
        category: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[CompanySetting], int]:
        """Return a page of settings for one company."""

        self._get_company(company_id)

        settings = self._setting_repository.list(
            company_id=company_id,
            category=category,
            limit=limit,
            offset=offset,
        )

        total = self._setting_repository.count(
            company_id=company_id,
            category=category,
        )

        return settings, total

    def delete_setting(
        self,
        *,
        company_id: UUID,
        category: str,
        key: str,
    ) -> None:
        """Delete one company setting."""

        setting = self.get_setting(
            company_id=company_id,
            category=category,
            key=key,
        )

        self._setting_repository.delete(setting)
        self._session.commit()


def get_company_setting_service(
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
) -> CompanySettingService:
    """Create a request-scoped CompanySetting service."""

    return CompanySettingService(
        setting_repository=CompanySettingRepository(session),
        company_repository=CompanyRepository(session),
        session=session,
    )
