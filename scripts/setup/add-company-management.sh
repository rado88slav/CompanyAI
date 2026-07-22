#!/usr/bin/env bash
# Description: Add company update, activation and deactivation operations.

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"

printf '%s\n' "======================================"
printf '%s\n' " Company AI - Add Company Management"
printf '%s\n' "======================================"
printf '\n'

printf '%s\n' "Updating Company API schemas..."

cat > "${BACKEND_DIR}/app/schemas/company.py" <<'PYTHON'
"""Pydantic schemas for the Company domain."""

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
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
        """Normalize and validate a company name."""

        normalized = " ".join(value.split())

        if len(normalized) < 2:
            raise ValueError(
                "Company name must contain at least two characters."
            )

        return normalized

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        """Normalize a valid company slug to lowercase."""

        return value.lower()


class CompanyUpdate(BaseModel):
    """Input data for partially updating a company."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=200,
        examples=["Updated Heating Systems"],
    )

    slug: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        examples=["updated-heating-systems"],
    )

    @field_validator("name")
    @classmethod
    def validate_name(
        cls,
        value: str | None,
    ) -> str | None:
        """Normalize and validate an optional company name."""

        if value is None:
            return None

        normalized = " ".join(value.split())

        if len(normalized) < 2:
            raise ValueError(
                "Company name must contain at least two characters."
            )

        return normalized

    @field_validator("slug")
    @classmethod
    def normalize_slug(
        cls,
        value: str | None,
    ) -> str | None:
        """Normalize an optional valid company slug."""

        if value is None:
            return None

        return value.lower()

    @model_validator(mode="after")
    def validate_update_payload(self) -> Self:
        """Require at least one non-null field."""

        update_fields = self.model_dump(
            exclude_unset=True,
        )

        if not update_fields:
            raise ValueError(
                "At least one company field must be provided."
            )

        if any(
            value is None
            for value in update_fields.values()
        ):
            raise ValueError(
                "Company update fields cannot be null."
            )

        return self


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
PYTHON

cat > "${BACKEND_DIR}/app/schemas/__init__.py" <<'PYTHON'
"""Company AI API schemas."""

from app.schemas.company import (
    CompanyCreate,
    CompanyListResponse,
    CompanyResponse,
    CompanyUpdate,
)

__all__ = [
    "CompanyCreate",
    "CompanyListResponse",
    "CompanyResponse",
    "CompanyUpdate",
]
PYTHON

printf '%s\n' "Updating Company repository..."

cat > "${BACKEND_DIR}/app/repositories/company.py" <<'PYTHON'
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
PYTHON

printf '%s\n' "Updating Company service..."

cat > "${BACKEND_DIR}/app/services/company.py" <<'PYTHON'
"""Application service for the Company domain."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.company import Company
from app.repositories.company import CompanyRepository
from app.schemas.company import (
    CompanyCreate,
    CompanyUpdate,
)


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

    def update_company(
        self,
        company_id: UUID,
        company_data: CompanyUpdate,
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

        try:
            updated_company = self._repository.update(
                company,
                company_data,
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()

            raise CompanySlugConflictError(
                "Company slug already exists."
            ) from exc

        return updated_company

    def activate_company(
        self,
        company_id: UUID,
    ) -> Company:
        """Activate a company and synchronize its status."""

        company = self.get_company(company_id)

        activated_company = self._repository.set_active(
            company,
            is_active=True,
        )

        self._session.commit()

        return activated_company

    def deactivate_company(
        self,
        company_id: UUID,
    ) -> Company:
        """Deactivate a company and synchronize its status."""

        company = self.get_company(company_id)

        deactivated_company = self._repository.set_active(
            company,
            is_active=False,
        )

        self._session.commit()

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
        session=session,
    )
PYTHON

printf '%s\n' "Updating Company API routes..."

cat > "${BACKEND_DIR}/app/api/routes/companies.py" <<'PYTHON'
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
    CompanyUpdate,
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


def company_not_found_exception(
    exc: CompanyNotFoundError,
) -> HTTPException:
    """Create the standard Company not-found response."""

    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Company was not found.",
    )


def company_slug_conflict_exception(
    exc: CompanySlugConflictError,
) -> HTTPException:
    """Create the standard Company slug-conflict response."""

    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A company with this slug already exists.",
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
        raise company_slug_conflict_exception(exc) from exc

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
        raise company_not_found_exception(exc) from exc

    return CompanyResponse.model_validate(company)


@router.patch(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Update a company",
)
def update_company(
    company_id: UUID,
    company_data: CompanyUpdate,
    service: Annotated[
        CompanyService,
        Depends(get_company_service),
    ],
) -> CompanyResponse:
    """Partially update a Company Context."""

    try:
        company = service.update_company(
            company_id,
            company_data,
        )
    except CompanyNotFoundError as exc:
        raise company_not_found_exception(exc) from exc
    except CompanySlugConflictError as exc:
        raise company_slug_conflict_exception(exc) from exc

    return CompanyResponse.model_validate(company)


@router.post(
    "/{company_id}/activate",
    response_model=CompanyResponse,
    summary="Activate a company",
)
def activate_company(
    company_id: UUID,
    service: Annotated[
        CompanyService,
        Depends(get_company_service),
    ],
) -> CompanyResponse:
    """Activate a Company Context."""

    try:
        company = service.activate_company(company_id)
    except CompanyNotFoundError as exc:
        raise company_not_found_exception(exc) from exc

    return CompanyResponse.model_validate(company)


@router.post(
    "/{company_id}/deactivate",
    response_model=CompanyResponse,
    summary="Deactivate a company",
)
def deactivate_company(
    company_id: UUID,
    service: Annotated[
        CompanyService,
        Depends(get_company_service),
    ],
) -> CompanyResponse:
    """Deactivate a Company Context."""

    try:
        company = service.deactivate_company(company_id)
    except CompanyNotFoundError as exc:
        raise company_not_found_exception(exc) from exc

    return CompanyResponse.model_validate(company)
PYTHON

printf '%s\n' "Updating Company domain tests..."

cat > "${BACKEND_DIR}/tests/test_company_domain.py" <<'PYTHON'
"""Tests for Company Context API behavior."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.models.company import CompanyStatus
from app.schemas.company import (
    CompanyCreate,
    CompanyUpdate,
)
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

    def update_company(
        self,
        company_id: UUID,
        company_data: CompanyUpdate,
    ) -> FakeCompany:
        company = self.get_company(company_id)

        if company_data.slug is not None:
            for existing_company in self.companies:
                if (
                    existing_company.id != company.id
                    and existing_company.slug == company_data.slug
                ):
                    raise CompanySlugConflictError

        update_fields = company_data.model_dump(
            exclude_unset=True,
        )

        for field_name, value in update_fields.items():
            setattr(company, field_name, value)

        company.updated_at = datetime.now(timezone.utc)

        return company

    def activate_company(
        self,
        company_id: UUID,
    ) -> FakeCompany:
        company = self.get_company(company_id)
        company.status = CompanyStatus.ACTIVE
        company.is_active = True
        company.updated_at = datetime.now(timezone.utc)

        return company

    def deactivate_company(
        self,
        company_id: UUID,
    ) -> FakeCompany:
        company = self.get_company(company_id)
        company.status = CompanyStatus.INACTIVE
        company.is_active = False
        company.updated_at = datetime.now(timezone.utc)

        return company


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


def test_update_company_name_and_slug() -> None:
    service = FakeCompanyService()

    company = service.create_company(
        CompanyCreate(
            name="Original Company",
            slug="original-company",
        )
    )

    try:
        with create_client(service) as client:
            response = client.patch(
                f"/api/v1/companies/{company.id}",
                json={
                    "name": "Updated Company",
                    "slug": "updated-company",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Company"
    assert response.json()["slug"] == "updated-company"


def test_update_company_slug_conflict() -> None:
    service = FakeCompanyService()

    first_company = service.create_company(
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
            response = client.patch(
                f"/api/v1/companies/{first_company.id}",
                json={
                    "slug": "second-company",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {
        "detail": "A company with this slug already exists."
    }


def test_empty_company_update_is_rejected() -> None:
    service = FakeCompanyService()

    company = service.create_company(
        CompanyCreate(
            name="Existing Company",
            slug="existing-company",
        )
    )

    try:
        with create_client(service) as client:
            response = client.patch(
                f"/api/v1/companies/{company.id}",
                json={},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_null_company_update_is_rejected() -> None:
    service = FakeCompanyService()

    company = service.create_company(
        CompanyCreate(
            name="Existing Company",
            slug="existing-company",
        )
    )

    try:
        with create_client(service) as client:
            response = client.patch(
                f"/api/v1/companies/{company.id}",
                json={
                    "name": None,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_update_missing_company_returns_not_found() -> None:
    service = FakeCompanyService()

    try:
        with create_client(service) as client:
            response = client.patch(
                f"/api/v1/companies/{uuid4()}",
                json={
                    "name": "Missing Company",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Company was not found."
    }


def test_deactivate_and_activate_company() -> None:
    service = FakeCompanyService()

    company = service.create_company(
        CompanyCreate(
            name="Status Company",
            slug="status-company",
        )
    )

    try:
        with create_client(service) as client:
            deactivate_response = client.post(
                f"/api/v1/companies/{company.id}/deactivate"
            )

            activate_response = client.post(
                f"/api/v1/companies/{company.id}/activate"
            )
    finally:
        app.dependency_overrides.clear()

    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["status"] == "inactive"
    assert deactivate_response.json()["is_active"] is False

    assert activate_response.status_code == 200
    assert activate_response.json()["status"] == "active"
    assert activate_response.json()["is_active"] is True


def test_activate_missing_company_returns_not_found() -> None:
    service = FakeCompanyService()

    try:
        with create_client(service) as client:
            response = client.post(
                f"/api/v1/companies/{uuid4()}/activate"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Company was not found."
    }
PYTHON

printf '\n%s\n' "Company management generated successfully."
printf '%s\n' "Updated files:"
printf '%s\n' "  - backend/app/schemas/company.py"
printf '%s\n' "  - backend/app/schemas/__init__.py"
printf '%s\n' "  - backend/app/repositories/company.py"
printf '%s\n' "  - backend/app/services/company.py"
printf '%s\n' "  - backend/app/api/routes/companies.py"
printf '%s\n' "  - backend/tests/test_company_domain.py"
printf '\n%s\n' "No database migration is required."
printf '%s\n' "Next step: validate and run the generator."
