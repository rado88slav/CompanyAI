#!/usr/bin/env bash
# Description: Add the Company domain model, migration, service layer and API to Company AI.

set -Eeuo pipefail

trap 'echo "Error: Company domain setup failed near line $LINENO." >&2' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"

MODEL_FILE="$BACKEND_DIR/app/models/company.py"
MODELS_INIT_FILE="$BACKEND_DIR/app/models/__init__.py"
SCHEMA_FILE="$BACKEND_DIR/app/schemas/company.py"
REPOSITORY_FILE="$BACKEND_DIR/app/repositories/company.py"
REPOSITORIES_INIT_FILE="$BACKEND_DIR/app/repositories/__init__.py"
SERVICE_FILE="$BACKEND_DIR/app/services/company.py"
ROUTE_FILE="$BACKEND_DIR/app/api/routes/companies.py"
ROUTER_FILE="$BACKEND_DIR/app/api/router.py"
MIGRATION_FILE="$BACKEND_DIR/migrations/versions/0002_create_companies_table.py"
DOMAIN_TEST_FILE="$BACKEND_DIR/tests/test_company_domain.py"
MIGRATION_TEST_FILE="$BACKEND_DIR/tests/test_migrations.py"

show_usage() {
    cat <<'USAGE'
Usage:
  ./scripts/setup/add-company-domain.sh

This script adds the initial Company Context domain:

  - SQLAlchemy Company model;
  - PostgreSQL migration 0002;
  - Pydantic request and response schemas;
  - repository layer;
  - application service layer;
  - FastAPI company endpoints;
  - company domain tests;
  - updated Alembic migration tests.

Generated API endpoints:

  POST /api/v1/companies
  GET  /api/v1/companies
  GET  /api/v1/companies/{company_id}
USAGE
}

if (($# > 0)); then
    case "$1" in
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            echo "Error: Unknown argument: $1" >&2
            show_usage >&2
            exit 1
            ;;
    esac
fi

echo "======================================"
echo " Company AI - Add Company Domain"
echo "======================================"

REQUIRED_FILES=(
    "$BACKEND_DIR/app/db/base.py"
    "$BACKEND_DIR/app/db/session.py"
    "$MODELS_INIT_FILE"
    "$BACKEND_DIR/app/schemas/__init__.py"
    "$BACKEND_DIR/app/services/__init__.py"
    "$ROUTER_FILE"
    "$BACKEND_DIR/migrations/versions/0001_initial_schema.py"
    "$MIGRATION_TEST_FILE"
    "$PROJECT_ROOT/docker-compose.yml"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo "Error: Required file is missing: $file" >&2
        exit 1
    fi
done

mkdir -p \
    "$BACKEND_DIR/app/repositories" \
    "$BACKEND_DIR/app/services" \
    "$BACKEND_DIR/app/schemas" \
    "$BACKEND_DIR/app/api/routes" \
    "$BACKEND_DIR/app/models" \
    "$BACKEND_DIR/migrations/versions" \
    "$BACKEND_DIR/tests"

echo
echo "Creating Company SQLAlchemy model..."

cat > "$MODEL_FILE" <<'EOF'
"""Company database model."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CompanyStatus(StrEnum):
    """Supported company lifecycle states."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class Company(Base):
    """A company context within the Company AI platform."""

    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_companies_status",
        ),
        Index(
            "ix_companies_name",
            "name",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CompanyStatus.ACTIVE.value,
        server_default=CompanyStatus.ACTIVE.value,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
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
EOF

echo "Registering Company metadata for Alembic..."

cat > "$MODELS_INIT_FILE" <<'EOF'
"""Company AI database models.

Every SQLAlchemy model must be imported here so Alembic can discover its
metadata during automatic migration generation.
"""

from app.models.company import Company, CompanyStatus

__all__ = [
    "Company",
    "CompanyStatus",
]
EOF

echo "Creating Company API schemas..."

cat > "$SCHEMA_FILE" <<'EOF'
"""Pydantic schemas for the Company domain."""

from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.models.company import CompanyStatus


class CompanyCreate(BaseModel):
    """Input data for creating a company."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    name: str = Field(
        min_length=2,
        max_length=200,
        examples=["Example Heating Systems"],
    )

    slug: str = Field(
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        examples=["example-heating-systems"],
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Reject names containing only whitespace."""

        normalized = " ".join(value.split())

        if len(normalized) < 2:
            raise ValueError(
                "Company name must contain at least two characters."
            )

        return normalized

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        """Normalize company slugs to lowercase."""

        return value.lower()


class CompanyResponse(BaseModel):
    """Public company response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    status: CompanyStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CompanyListResponse(BaseModel):
    """Paginated company collection response."""

    items: list[CompanyResponse]
    total: int
    limit: int
    offset: int
EOF

cat > "$BACKEND_DIR/app/schemas/__init__.py" <<'EOF'
"""Company AI API schemas."""

from app.schemas.company import (
    CompanyCreate,
    CompanyListResponse,
    CompanyResponse,
)

__all__ = [
    "CompanyCreate",
    "CompanyListResponse",
    "CompanyResponse",
]
EOF

echo "Creating Company repository..."

cat > "$REPOSITORIES_INIT_FILE" <<'EOF'
"""Database repository package."""
EOF

cat > "$REPOSITORY_FILE" <<'EOF'
"""Persistence operations for Company records."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.schemas.company import CompanyCreate


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
EOF

echo "Creating Company service..."

cat > "$SERVICE_FILE" <<'EOF'
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
EOF

cat > "$BACKEND_DIR/app/services/__init__.py" <<'EOF'
"""Application service package."""

from app.services.company import (
    CompanyNotFoundError,
    CompanyService,
    CompanySlugConflictError,
    get_company_service,
)

__all__ = [
    "CompanyNotFoundError",
    "CompanyService",
    "CompanySlugConflictError",
    "get_company_service",
]
EOF

echo "Creating Company API routes..."

cat > "$ROUTE_FILE" <<'EOF'
"""HTTP endpoints for Company Context management."""

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from app.schemas.company import (
    CompanyCreate,
    CompanyListResponse,
    CompanyResponse,
)
from app.services.company import (
    CompanyNotFoundError,
    CompanyService,
    CompanySlugConflictError,
    get_company_service,
)

router = APIRouter(
    prefix="/companies",
    tags=["companies"],
)


@router.post(
    "",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a company",
)
def create_company(
    company_data: CompanyCreate,
    service: Annotated[
        CompanyService,
        Depends(get_company_service),
    ],
) -> CompanyResponse:
    """Create a new Company Context."""

    try:
        company = service.create_company(company_data)
    except CompanySlugConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A company with this slug already exists.",
        ) from exc

    return CompanyResponse.model_validate(company)


@router.get(
    "",
    response_model=CompanyListResponse,
    summary="List companies",
)
def list_companies(
    service: Annotated[
        CompanyService,
        Depends(get_company_service),
    ],
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> CompanyListResponse:
    """Return a paginated collection of companies."""

    companies, total = service.list_companies(
        limit=limit,
        offset=offset,
    )

    return CompanyListResponse(
        items=[
            CompanyResponse.model_validate(company)
            for company in companies
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Get a company",
)
def get_company(
    company_id: UUID,
    service: Annotated[
        CompanyService,
        Depends(get_company_service),
    ],
) -> CompanyResponse:
    """Return one Company Context by UUID."""

    try:
        company = service.get_company(company_id)
    except CompanyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company was not found.",
        ) from exc

    return CompanyResponse.model_validate(company)
EOF

echo "Registering Company API router..."

cat > "$ROUTER_FILE" <<'EOF'
"""Main API router."""

from fastapi import APIRouter

from app.api.routes.companies import router as companies_router
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(companies_router)
EOF

echo "Creating Company database migration..."

cat > "$MIGRATION_FILE" <<'EOF'
"""Create companies table.

Revision ID: 0002_companies
Revises: 0001_initial
Create Date: 2026-07-22
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_companies"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the companies table and indexes."""

    op.create_table(
        "companies",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=200),
            nullable=False,
        ),
        sa.Column(
            "slug",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
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
            "status IN ('active', 'inactive')",
            name="ck_companies_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "slug",
            name="uq_companies_slug",
        ),
    )

    op.create_index(
        "ix_companies_name",
        "companies",
        ["name"],
        unique=False,
    )

    op.create_index(
        "ix_companies_slug",
        "companies",
        ["slug"],
        unique=True,
    )


def downgrade() -> None:
    """Remove the companies table."""

    op.drop_index(
        "ix_companies_slug",
        table_name="companies",
    )

    op.drop_index(
        "ix_companies_name",
        table_name="companies",
    )

    op.drop_table("companies")
EOF

echo "Updating migration validation tests..."

cat > "$MIGRATION_TEST_FILE" <<'EOF'
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
        "0002_companies"
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
EOF

echo "Creating Company domain tests..."

cat > "$DOMAIN_TEST_FILE" <<'EOF'
"""Tests for Company Context API behavior."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.models.company import CompanyStatus
from app.schemas.company import CompanyCreate
from app.services.company import (
    CompanyNotFoundError,
    CompanySlugConflictError,
    get_company_service,
)

NOW = datetime.now(timezone.utc)


class FakeCompany:
    """Simple object compatible with CompanyResponse validation."""

    def __init__(
        self,
        *,
        company_id: UUID,
        name: str,
        slug: str,
    ) -> None:
        self.id = company_id
        self.name = name
        self.slug = slug
        self.status = CompanyStatus.ACTIVE
        self.is_active = True
        self.created_at = NOW
        self.updated_at = NOW


class FakeCompanyService:
    """In-memory Company service used by API tests."""

    def __init__(self) -> None:
        self.companies: list[FakeCompany] = []

    def create_company(
        self,
        company_data: CompanyCreate,
    ) -> FakeCompany:
        for company in self.companies:
            if company.slug == company_data.slug:
                raise CompanySlugConflictError

        company = FakeCompany(
            company_id=uuid4(),
            name=company_data.name,
            slug=company_data.slug,
        )

        self.companies.append(company)

        return company

    def get_company(
        self,
        company_id: UUID,
    ) -> FakeCompany:
        for company in self.companies:
            if company.id == company_id:
                return company

        raise CompanyNotFoundError

    def list_companies(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[FakeCompany], int]:
        return (
            self.companies[offset:offset + limit],
            len(self.companies),
        )


def create_client(
    service: FakeCompanyService,
) -> TestClient:
    """Create a client with the Company service overridden."""

    app.dependency_overrides[get_company_service] = (
        lambda: service
    )

    return TestClient(app)


def test_create_and_get_company() -> None:
    service = FakeCompanyService()

    try:
        with create_client(service) as client:
            create_response = client.post(
                "/api/v1/companies",
                json={
                    "name": "Example Heating Systems",
                    "slug": "example-heating-systems",
                },
            )

            assert create_response.status_code == 201

            created_company = create_response.json()

            get_response = client.get(
                f"/api/v1/companies/{created_company['id']}"
            )
    finally:
        app.dependency_overrides.clear()

    assert get_response.status_code == 200
    assert get_response.json()["name"] == (
        "Example Heating Systems"
    )
    assert get_response.json()["slug"] == (
        "example-heating-systems"
    )
    assert get_response.json()["status"] == "active"


def test_list_companies() -> None:
    service = FakeCompanyService()

    service.create_company(
        CompanyCreate(
            name="First Company",
            slug="first-company",
        )
    )

    service.create_company(
        CompanyCreate(
            name="Second Company",
            slug="second-company",
        )
    )

    try:
        with create_client(service) as client:
            response = client.get(
                "/api/v1/companies?limit=1&offset=1"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["limit"] == 1
    assert response.json()["offset"] == 1
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["slug"] == (
        "second-company"
    )


def test_duplicate_company_slug_returns_conflict() -> None:
    service = FakeCompanyService()

    service.create_company(
        CompanyCreate(
            name="Existing Company",
            slug="existing-company",
        )
    )

    try:
        with create_client(service) as client:
            response = client.post(
                "/api/v1/companies",
                json={
                    "name": "Another Company",
                    "slug": "existing-company",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {
        "detail": "A company with this slug already exists."
    }


def test_missing_company_returns_not_found() -> None:
    service = FakeCompanyService()

    try:
        with create_client(service) as client:
            response = client.get(
                f"/api/v1/companies/{uuid4()}"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Company was not found."
    }


def test_invalid_company_slug_is_rejected() -> None:
    service = FakeCompanyService()

    try:
        with create_client(service) as client:
            response = client.post(
                "/api/v1/companies",
                json={
                    "name": "Invalid Slug Company",
                    "slug": "Invalid Slug!",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
EOF

echo
echo "Company domain created successfully."
echo
echo "Generated or updated files:"
echo "  - backend/app/models/company.py"
echo "  - backend/app/models/__init__.py"
echo "  - backend/app/schemas/company.py"
echo "  - backend/app/schemas/__init__.py"
echo "  - backend/app/repositories/__init__.py"
echo "  - backend/app/repositories/company.py"
echo "  - backend/app/services/company.py"
echo "  - backend/app/services/__init__.py"
echo "  - backend/app/api/routes/companies.py"
echo "  - backend/app/api/router.py"
echo "  - backend/migrations/versions/0002_create_companies_table.py"
echo "  - backend/tests/test_company_domain.py"
echo "  - backend/tests/test_migrations.py"
echo
echo "No migration has been applied yet."
echo "The backend image has not been rebuilt yet."
echo "Next step: validate the Bash, Python and migration syntax."