"""Persistence operations for company-owned settings."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company_setting import CompanySetting
from app.schemas.company_setting import CompanySettingUpsert


class CompanySettingRepository:
    """Access CompanySetting records through a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        company_id: UUID,
        category: str,
        key: str,
        setting_data: CompanySettingUpsert,
    ) -> CompanySetting:
        """Create and flush a company setting."""

        setting = CompanySetting(
            company_id=company_id,
            category=category,
            key=key,
            value=setting_data.value,
        )

        self._session.add(setting)
        self._session.flush()
        self._session.refresh(setting)

        return setting

    def get(
        self,
        *,
        company_id: UUID,
        category: str,
        key: str,
    ) -> CompanySetting | None:
        """Return one setting by its company, category and key."""

        statement = select(CompanySetting).where(
            CompanySetting.company_id == company_id,
            CompanySetting.category == category,
            CompanySetting.key == key,
        )

        return self._session.scalar(statement)

    def list(
        self,
        *,
        company_id: UUID,
        category: str | None,
        limit: int,
        offset: int,
    ) -> list[CompanySetting]:
        """Return company settings in deterministic order."""

        statement = select(CompanySetting).where(
            CompanySetting.company_id == company_id,
        )

        if category is not None:
            statement = statement.where(
                CompanySetting.category == category,
            )

        statement = (
            statement
            .order_by(
                CompanySetting.category.asc(),
                CompanySetting.key.asc(),
                CompanySetting.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )

        return list(
            self._session.scalars(statement).all()
        )

    def count(
        self,
        *,
        company_id: UUID,
        category: str | None,
    ) -> int:
        """Return the number of matching company settings."""

        statement = select(func.count()).select_from(
            CompanySetting
        ).where(
            CompanySetting.company_id == company_id,
        )

        if category is not None:
            statement = statement.where(
                CompanySetting.category == category,
            )

        return int(
            self._session.scalar(statement) or 0
        )

    def replace_value(
        self,
        setting: CompanySetting,
        setting_data: CompanySettingUpsert,
    ) -> CompanySetting:
        """Replace a setting value and flush the record."""

        setting.value = setting_data.value

        self._session.flush()
        self._session.refresh(setting)

        return setting

    def delete(
        self,
        setting: CompanySetting,
    ) -> None:
        """Delete and flush a company setting."""

        self._session.delete(setting)
        self._session.flush()
