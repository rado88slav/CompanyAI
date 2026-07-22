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
