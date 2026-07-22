#!/usr/bin/env bash
# Description: Add company-owned settings storage, API operations and migration.

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"

printf '%s\n' "======================================"
printf '%s\n' " Company AI - Add Company Settings"
printf '%s\n' "======================================"
printf '\n'

printf '%s\n' "Creating CompanySetting SQLAlchemy model..."

cat > "${BACKEND_DIR}/app/models/company_setting.py" <<'PYTHON'
"""Company-owned setting database model."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CompanySetting(Base):
    """A non-secret configuration value owned by one company."""

    __tablename__ = "company_settings"
    __table_args__ = (
        CheckConstraint(
            "length(category) > 0",
            name="ck_company_settings_category_not_empty",
        ),
        CheckConstraint(
            "length(key) > 0",
            name="ck_company_settings_key_not_empty",
        ),
        UniqueConstraint(
            "company_id",
            "category",
            "key",
            name="uq_company_settings_company_category_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "companies.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    value: Mapped[Any] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
PYTHON

printf '%s\n' "Registering CompanySetting metadata..."

cat > "${BACKEND_DIR}/app/models/__init__.py" <<'PYTHON'
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
PYTHON

printf '%s\n' "Creating CompanySetting API schemas..."

cat > "${BACKEND_DIR}/app/schemas/company_setting.py" <<'PYTHON'
"""Pydantic schemas for company-owned settings."""

from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
)


class CompanySettingUpsert(BaseModel):
    """Input value for creating or replacing a company setting."""

    model_config = ConfigDict(
        extra="forbid",
    )

    value: JsonValue = Field(
        examples=[
            {
                "timezone": "Europe/Sofia",
            }
        ],
    )


class CompanySettingResponse(BaseModel):
    """Public company setting response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    category: str
    key: str
    value: JsonValue
    created_at: datetime
    updated_at: datetime


class CompanySettingListResponse(BaseModel):
    """Paginated company setting collection."""

    items: list[CompanySettingResponse]
    total: int
    limit: int
    offset: int
PYTHON

cat > "${BACKEND_DIR}/app/schemas/__init__.py" <<'PYTHON'
"""Company AI API schemas."""

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
    "CompanyCreate",
    "CompanyListResponse",
    "CompanyResponse",
    "CompanySettingListResponse",
    "CompanySettingResponse",
    "CompanySettingUpsert",
    "CompanyUpdate",
]
PYTHON

printf '%s\n' "Creating CompanySetting repository..."

cat > "${BACKEND_DIR}/app/repositories/company_setting.py" <<'PYTHON'
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
PYTHON

cat > "${BACKEND_DIR}/app/repositories/__init__.py" <<'PYTHON'
"""Database repository package."""

from app.repositories.company import CompanyRepository
from app.repositories.company_setting import (
    CompanySettingRepository,
)

__all__ = [
    "CompanyRepository",
    "CompanySettingRepository",
]
PYTHON

printf '%s\n' "Creating CompanySetting service..."

cat > "${BACKEND_DIR}/app/services/company_setting.py" <<'PYTHON'
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
PYTHON

cat > "${BACKEND_DIR}/app/services/__init__.py" <<'PYTHON'
"""Application service package."""

from app.services.company import (
    CompanyNotFoundError,
    CompanyService,
    CompanySlugConflictError,
    get_company_service,
)
from app.services.company_setting import (
    CompanySettingNotFoundError,
    CompanySettingService,
    get_company_setting_service,
)

__all__ = [
    "CompanyNotFoundError",
    "CompanyService",
    "CompanySettingNotFoundError",
    "CompanySettingService",
    "CompanySlugConflictError",
    "get_company_service",
    "get_company_setting_service",
]
PYTHON

printf '%s\n' "Creating CompanySetting API routes..."

cat > "${BACKEND_DIR}/app/api/routes/company_settings.py" <<'PYTHON'
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
PYTHON

printf '%s\n' "Registering CompanySetting API router..."

cat > "${BACKEND_DIR}/app/api/router.py" <<'PYTHON'
"""Main API router."""

from fastapi import APIRouter

from app.api.routes.companies import router as companies_router
from app.api.routes.company_settings import (
    router as company_settings_router,
)
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(companies_router)
api_router.include_router(company_settings_router)
PYTHON

printf '%s\n' "Creating CompanySetting database migration..."

cat > "${BACKEND_DIR}/migrations/versions/0003_create_company_settings_table.py" <<'PYTHON'
"""Create company settings table.

Revision ID: 0003_company_settings
Revises: 0002_companies
Create Date: 2026-07-22
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_company_settings"
down_revision: Union[str, Sequence[str], None] = (
    "0002_companies"
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the company_settings table and indexes."""

    op.create_table(
        "company_settings",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "key",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "value",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(category) > 0",
            name="ck_company_settings_category_not_empty",
        ),
        sa.CheckConstraint(
            "length(key) > 0",
            name="ck_company_settings_key_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_company_settings_company_id_companies",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "category",
            "key",
            name="uq_company_settings_company_category_key",
        ),
    )


def downgrade() -> None:
    """Remove the company_settings table."""

    op.drop_table("company_settings")
PYTHON

printf '%s\n' "Updating migration validation tests..."

cat > "${BACKEND_DIR}/tests/test_migrations.py" <<'PYTHON'
"""Tests for the Alembic migration configuration."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def create_alembic_config() -> Config:
    """Create an Alembic configuration for file-based validation."""

    return Config(str(BACKEND_ROOT / "alembic.ini"))


def test_migration_history_has_one_head() -> None:
    """The migration graph must never contain multiple heads."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )

    assert script_directory.get_heads() == [
        "0003_company_settings"
    ]


def test_initial_migration_is_available() -> None:
    """The initial migration must remain discoverable."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )

    revision = script_directory.get_revision(
        "0001_initial"
    )

    assert revision is not None
    assert revision.down_revision is None


def test_company_migration_follows_initial_revision() -> None:
    """The Company migration must follow the baseline."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )

    revision = script_directory.get_revision(
        "0002_companies"
    )

    assert revision is not None
    assert revision.down_revision == "0001_initial"


def test_company_settings_migration_follows_company_revision() -> None:
    """Company settings must follow the Company migration."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )

    revision = script_directory.get_revision(
        "0003_company_settings"
    )

    assert revision is not None
    assert revision.down_revision == "0002_companies"
PYTHON

printf '%s\n' "Creating CompanySetting API tests..."

cat > "${BACKEND_DIR}/tests/test_company_settings.py" <<'PYTHON'
"""Tests for company-owned setting API behavior."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.company_setting import CompanySettingUpsert
from app.services.company import CompanyNotFoundError
from app.services.company_setting import (
    CompanySettingNotFoundError,
    get_company_setting_service,
)

NOW = datetime.now(timezone.utc)


class FakeCompanySetting:
    """Object compatible with CompanySettingResponse validation."""

    def __init__(
        self,
        *,
        setting_id: UUID,
        company_id: UUID,
        category: str,
        key: str,
        value: Any,
    ) -> None:
        self.id = setting_id
        self.company_id = company_id
        self.category = category
        self.key = key
        self.value = value
        self.created_at = NOW
        self.updated_at = NOW


class FakeCompanySettingService:
    """In-memory service used by CompanySetting API tests."""

    def __init__(
        self,
        company_ids: set[UUID],
    ) -> None:
        self.company_ids = company_ids
        self.settings: dict[
            tuple[UUID, str, str],
            FakeCompanySetting,
        ] = {}

    def _require_company(
        self,
        company_id: UUID,
    ) -> None:
        """Reject operations for an unknown company."""

        if company_id not in self.company_ids:
            raise CompanyNotFoundError

    def upsert_setting(
        self,
        *,
        company_id: UUID,
        category: str,
        key: str,
        setting_data: CompanySettingUpsert,
    ) -> FakeCompanySetting:
        """Create or replace one in-memory setting."""

        self._require_company(company_id)

        identity = (
            company_id,
            category,
            key,
        )

        setting = self.settings.get(identity)

        if setting is None:
            setting = FakeCompanySetting(
                setting_id=uuid4(),
                company_id=company_id,
                category=category,
                key=key,
                value=setting_data.value,
            )

            self.settings[identity] = setting
        else:
            setting.value = setting_data.value
            setting.updated_at = datetime.now(timezone.utc)

        return setting

    def get_setting(
        self,
        *,
        company_id: UUID,
        category: str,
        key: str,
    ) -> FakeCompanySetting:
        """Return one in-memory setting."""

        self._require_company(company_id)

        setting = self.settings.get(
            (
                company_id,
                category,
                key,
            )
        )

        if setting is None:
            raise CompanySettingNotFoundError

        return setting

    def list_settings(
        self,
        *,
        company_id: UUID,
        category: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[FakeCompanySetting], int]:
        """Return one page of sorted in-memory settings."""

        self._require_company(company_id)

        matching_settings = [
            setting
            for setting in self.settings.values()
            if setting.company_id == company_id
            and (
                category is None
                or setting.category == category
            )
        ]

        matching_settings.sort(
            key=lambda setting: (
                setting.category,
                setting.key,
                str(setting.id),
            )
        )

        return (
            matching_settings[offset:offset + limit],
            len(matching_settings),
        )

    def delete_setting(
        self,
        *,
        company_id: UUID,
        category: str,
        key: str,
    ) -> None:
        """Delete one in-memory setting."""

        setting = self.get_setting(
            company_id=company_id,
            category=category,
            key=key,
        )

        del self.settings[
            (
                setting.company_id,
                setting.category,
                setting.key,
            )
        ]


def create_client(
    service: FakeCompanySettingService,
) -> TestClient:
    """Create a client with the setting service overridden."""

    app.dependency_overrides[
        get_company_setting_service
    ] = lambda: service

    return TestClient(app)


def test_upsert_and_get_company_setting() -> None:
    company_id = uuid4()

    service = FakeCompanySettingService(
        company_ids={company_id},
    )

    try:
        with create_client(service) as client:
            upsert_response = client.put(
                (
                    f"/api/v1/companies/{company_id}"
                    "/settings/general/timezone"
                ),
                json={
                    "value": "Europe/Sofia",
                },
            )

            get_response = client.get(
                (
                    f"/api/v1/companies/{company_id}"
                    "/settings/general/timezone"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert upsert_response.status_code == 200
    assert get_response.status_code == 200
    assert get_response.json()["company_id"] == str(
        company_id
    )
    assert get_response.json()["category"] == "general"
    assert get_response.json()["key"] == "timezone"
    assert get_response.json()["value"] == "Europe/Sofia"


def test_upsert_replaces_existing_setting_value() -> None:
    company_id = uuid4()

    service = FakeCompanySettingService(
        company_ids={company_id},
    )

    try:
        with create_client(service) as client:
            first_response = client.put(
                (
                    f"/api/v1/companies/{company_id}"
                    "/settings/ai/model"
                ),
                json={
                    "value": "first-model",
                },
            )

            second_response = client.put(
                (
                    f"/api/v1/companies/{company_id}"
                    "/settings/ai/model"
                ),
                json={
                    "value": "second-model",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["id"] == (
        second_response.json()["id"]
    )
    assert second_response.json()["value"] == (
        "second-model"
    )
    assert len(service.settings) == 1


def test_list_company_settings_with_category_filter() -> None:
    company_id = uuid4()

    service = FakeCompanySettingService(
        company_ids={company_id},
    )

    service.upsert_setting(
        company_id=company_id,
        category="general",
        key="timezone",
        setting_data=CompanySettingUpsert(
            value="Europe/Sofia",
        ),
    )

    service.upsert_setting(
        company_id=company_id,
        category="email",
        key="provider",
        setting_data=CompanySettingUpsert(
            value="test-provider",
        ),
    )

    service.upsert_setting(
        company_id=company_id,
        category="email",
        key="daily-limit",
        setting_data=CompanySettingUpsert(
            value=50,
        ),
    )

    try:
        with create_client(service) as client:
            response = client.get(
                (
                    f"/api/v1/companies/{company_id}/settings"
                    "?category=email&limit=1&offset=1"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["limit"] == 1
    assert response.json()["offset"] == 1
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["category"] == (
        "email"
    )
PYTHON

cat >> "${BACKEND_DIR}/tests/test_company_settings.py" <<'PYTHON'


def test_settings_are_isolated_between_companies() -> None:
    first_company_id = uuid4()
    second_company_id = uuid4()

    service = FakeCompanySettingService(
        company_ids={
            first_company_id,
            second_company_id,
        },
    )

    service.upsert_setting(
        company_id=first_company_id,
        category="general",
        key="timezone",
        setting_data=CompanySettingUpsert(
            value="Europe/Sofia",
        ),
    )

    service.upsert_setting(
        company_id=second_company_id,
        category="general",
        key="timezone",
        setting_data=CompanySettingUpsert(
            value="Europe/Bucharest",
        ),
    )

    try:
        with create_client(service) as client:
            response = client.get(
                (
                    f"/api/v1/companies/{first_company_id}"
                    "/settings"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["company_id"] == (
        str(first_company_id)
    )
    assert response.json()["items"][0]["value"] == (
        "Europe/Sofia"
    )


def test_delete_company_setting() -> None:
    company_id = uuid4()

    service = FakeCompanySettingService(
        company_ids={company_id},
    )

    service.upsert_setting(
        company_id=company_id,
        category="general",
        key="timezone",
        setting_data=CompanySettingUpsert(
            value="Europe/Sofia",
        ),
    )

    try:
        with create_client(service) as client:
            delete_response = client.delete(
                (
                    f"/api/v1/companies/{company_id}"
                    "/settings/general/timezone"
                )
            )

            get_response = client.get(
                (
                    f"/api/v1/companies/{company_id}"
                    "/settings/general/timezone"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert get_response.status_code == 404
    assert get_response.json() == {
        "detail": "Company setting was not found."
    }


def test_missing_company_setting_returns_not_found() -> None:
    company_id = uuid4()

    service = FakeCompanySettingService(
        company_ids={company_id},
    )

    try:
        with create_client(service) as client:
            response = client.get(
                (
                    f"/api/v1/companies/{company_id}"
                    "/settings/general/missing-setting"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Company setting was not found."
    }


def test_unknown_company_returns_not_found() -> None:
    service = FakeCompanySettingService(
        company_ids=set(),
    )

    try:
        with create_client(service) as client:
            response = client.get(
                (
                    f"/api/v1/companies/{uuid4()}"
                    "/settings"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Company was not found."
    }


def test_invalid_setting_category_is_rejected() -> None:
    company_id = uuid4()

    service = FakeCompanySettingService(
        company_ids={company_id},
    )

    try:
        with create_client(service) as client:
            response = client.put(
                (
                    f"/api/v1/companies/{company_id}"
                    "/settings/Invalid Category/timezone"
                ),
                json={
                    "value": "Europe/Sofia",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
PYTHON

printf '\n%s\n' "Company Settings generated successfully."
printf '%s\n' "Generated or updated files:"
printf '%s\n' "  - backend/app/models/company_setting.py"
printf '%s\n' "  - backend/app/models/__init__.py"
printf '%s\n' "  - backend/app/schemas/company_setting.py"
printf '%s\n' "  - backend/app/schemas/__init__.py"
printf '%s\n' "  - backend/app/repositories/company_setting.py"
printf '%s\n' "  - backend/app/repositories/__init__.py"
printf '%s\n' "  - backend/app/services/company_setting.py"
printf '%s\n' "  - backend/app/services/__init__.py"
printf '%s\n' "  - backend/app/api/routes/company_settings.py"
printf '%s\n' "  - backend/app/api/router.py"
printf '%s\n' "  - backend/migrations/versions/0003_create_company_settings_table.py"
printf '%s\n' "  - backend/tests/test_company_settings.py"
printf '%s\n' "  - backend/tests/test_migrations.py"
printf '\n%s\n' "No migration has been applied yet."
printf '%s\n' "The backend image has not been rebuilt yet."
printf '%s\n' "Next step: validate and run the generator."
