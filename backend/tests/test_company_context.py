"""Tests for stateless active company context and path isolation."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.authentication import require_current_administrator
from app.main import app
from app.models.company import CompanyStatus
from app.services.company import CompanyNotFoundError, get_company_service
from app.services.company_setting import get_company_setting_service

NOW = datetime.now(timezone.utc)


class FakeAdministrator:
    """Administrator attributes used by company-context dependencies."""

    def __init__(self, *, is_superuser: bool) -> None:
        self.id = uuid4()
        self.is_active = True
        self.is_superuser = is_superuser


class FakeCompany:
    """Company attributes compatible with CompanyResponse validation."""

    def __init__(self, *, company_id: UUID, is_active: bool = True) -> None:
        self.id = company_id
        self.name = f"Company {company_id}"
        self.slug = f"company-{str(company_id)[:8]}"
        self.status = (
            CompanyStatus.ACTIVE.value
            if is_active
            else CompanyStatus.INACTIVE.value
        )
        self.is_active = is_active
        self.created_at = NOW
        self.updated_at = NOW


class FakeMembership:
    """Company membership attributes used by context resolution tests."""

    def __init__(
        self,
        *,
        company_id: UUID,
        administrator_id: UUID,
        role: str,
        is_active: bool = True,
    ) -> None:
        self.company_id = company_id
        self.administrator_id = administrator_id
        self.role = role
        self.is_active = is_active


class FakeCompanyService:
    """Resolve companies without database access."""

    def __init__(
        self,
        companies: list[FakeCompany],
        memberships: list[FakeMembership] | None = None,
    ) -> None:
        self.companies = {company.id: company for company in companies}
        self.memberships = memberships or []

    def get_company(self, company_id: UUID) -> FakeCompany:
        company = self.companies.get(company_id)

        if company is None:
            raise CompanyNotFoundError

        return company

    def get_active_membership(
        self,
        *,
        company_id: UUID,
        administrator_id: UUID,
    ) -> FakeMembership | None:
        for membership in self.memberships:
            if (
                membership.company_id == company_id
                and membership.administrator_id == administrator_id
                and membership.is_active
            ):
                return membership
        return None

    def list_available_company_contexts(
        self,
        *,
        administrator_id: UUID,
        is_superuser: bool,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[tuple[FakeCompany, FakeMembership | None]], int]:
        active_companies = [
            company
            for company in self.companies.values()
            if company.is_active and company.status == CompanyStatus.ACTIVE.value
        ]
        if is_superuser:
            items = [(company, None) for company in active_companies]
            return items[offset : offset + limit], len(items)

        items: list[tuple[FakeCompany, FakeMembership | None]] = []
        for membership in self.memberships:
            company = self.companies.get(membership.company_id)
            if (
                membership.administrator_id == administrator_id
                and membership.is_active
                and company is not None
                and company.is_active
            ):
                items.append((company, membership))
        return items[offset : offset + limit], len(items)


class RecordingSettingService:
    """Record whether an isolated setting operation reached its service."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_setting(self, **_kwargs: object) -> object:
        self.calls.append("get")
        raise AssertionError("Mismatched context reached the setting service.")

    def upsert_setting(self, **_kwargs: object) -> object:
        self.calls.append("upsert")
        raise AssertionError("Mismatched context reached the setting service.")

    def delete_setting(self, **_kwargs: object) -> None:
        self.calls.append("delete")
        raise AssertionError("Mismatched context reached the setting service.")


def create_client(
    *,
    administrator: FakeAdministrator,
    companies: list[FakeCompany],
    memberships: list[FakeMembership] | None = None,
    setting_service: RecordingSettingService | None = None,
) -> TestClient:
    """Create a client with authentication and services overridden."""

    app.dependency_overrides[require_current_administrator] = (
        lambda: administrator
    )
    app.dependency_overrides[get_company_service] = (
        lambda: FakeCompanyService(companies, memberships)
    )

    if setting_service is not None:
        app.dependency_overrides[get_company_setting_service] = (
            lambda: setting_service
        )

    return TestClient(app)


def test_missing_company_header_is_rejected() -> None:
    try:
        with create_client(
            administrator=FakeAdministrator(is_superuser=True),
            companies=[],
        ) as client:
            response = client.get("/api/v1/company-context")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "X-Company-ID header is required."


def test_invalid_company_header_is_rejected() -> None:
    try:
        with create_client(
            administrator=FakeAdministrator(is_superuser=True),
            companies=[],
        ) as client:
            response = client.get(
                "/api/v1/company-context",
                headers={"X-Company-ID": "not-a-uuid"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "valid company UUID" in response.json()["detail"]


def test_non_superuser_cannot_select_company_context() -> None:
    company = FakeCompany(company_id=uuid4())

    try:
        with create_client(
            administrator=FakeAdministrator(is_superuser=False),
            companies=[company],
        ) as client:
            response = client.get(
                "/api/v1/company-context",
                headers={"X-Company-ID": str(company.id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_unknown_company_context_is_rejected() -> None:
    try:
        with create_client(
            administrator=FakeAdministrator(is_superuser=True),
            companies=[],
        ) as client:
            response = client.get(
                "/api/v1/company-context",
                headers={"X-Company-ID": str(uuid4())},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_inactive_company_context_is_rejected() -> None:
    company = FakeCompany(company_id=uuid4(), is_active=False)

    try:
        with create_client(
            administrator=FakeAdministrator(is_superuser=True),
            companies=[company],
        ) as client:
            response = client.get(
                "/api/v1/company-context",
                headers={"X-Company-ID": str(company.id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409


def test_company_context_endpoint_returns_selected_company() -> None:
    company = FakeCompany(company_id=uuid4())

    try:
        with create_client(
            administrator=FakeAdministrator(is_superuser=True),
            companies=[company],
        ) as client:
            response = client.get(
                "/api/v1/company-context",
                headers={"X-Company-ID": str(company.id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["company"]["id"] == str(company.id)
    assert response.json()["company"]["status"] == "active"
    assert response.json()["membership_role"] is None
    assert response.json()["is_platform_superuser"] is True


def test_available_company_contexts_for_superuser_include_active_companies_only() -> None:
    active_company = FakeCompany(company_id=uuid4())
    inactive_company = FakeCompany(company_id=uuid4(), is_active=False)

    try:
        with create_client(
            administrator=FakeAdministrator(is_superuser=True),
            companies=[active_company, inactive_company],
        ) as client:
            response = client.get("/api/v1/company-context/available-companies")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["company"]["id"] == str(active_company.id)
    assert payload["items"][0]["membership_role"] is None
    assert payload["items"][0]["is_platform_superuser"] is True


def test_available_company_contexts_for_administrator_are_membership_scoped() -> None:
    administrator = FakeAdministrator(is_superuser=False)
    company_a = FakeCompany(company_id=uuid4())
    company_b = FakeCompany(company_id=uuid4())
    company_c = FakeCompany(company_id=uuid4(), is_active=False)
    memberships = [
        FakeMembership(
            company_id=company_a.id,
            administrator_id=administrator.id,
            role="admin",
        ),
        FakeMembership(
            company_id=company_b.id,
            administrator_id=uuid4(),
            role="owner",
        ),
        FakeMembership(
            company_id=company_c.id,
            administrator_id=administrator.id,
            role="owner",
        ),
    ]

    try:
        with create_client(
            administrator=administrator,
            companies=[company_a, company_b, company_c],
            memberships=memberships,
        ) as client:
            response = client.get("/api/v1/company-context/available-companies")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["company"]["id"] == str(company_a.id)
    assert payload["items"][0]["membership_role"] == "admin"
    assert payload["items"][0]["is_platform_superuser"] is False


def test_superuser_context_returns_real_active_owner_membership() -> None:
    company = FakeCompany(company_id=uuid4())
    administrator = FakeAdministrator(is_superuser=True)
    membership = FakeMembership(
        company_id=company.id,
        administrator_id=administrator.id,
        role="owner",
    )

    try:
        with create_client(
            administrator=administrator,
            companies=[company],
            memberships=[membership],
        ) as client:
            response = client.get(
                "/api/v1/company-context",
                headers={"X-Company-ID": str(company.id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["membership_role"] == "owner"
    assert response.json()["is_platform_superuser"] is True


def test_ordinary_administrator_context_returns_real_membership_role() -> None:
    company = FakeCompany(company_id=uuid4())
    administrator = FakeAdministrator(is_superuser=False)
    membership = FakeMembership(
        company_id=company.id,
        administrator_id=administrator.id,
        role="operator",
    )

    try:
        with create_client(
            administrator=administrator,
            companies=[company],
            memberships=[membership],
        ) as client:
            response = client.get(
                "/api/v1/company-context",
                headers={"X-Company-ID": str(company.id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["membership_role"] == "operator"
    assert response.json()["is_platform_superuser"] is False


def test_inactive_membership_is_not_exposed_for_superuser_context() -> None:
    company = FakeCompany(company_id=uuid4())
    administrator = FakeAdministrator(is_superuser=True)
    membership = FakeMembership(
        company_id=company.id,
        administrator_id=administrator.id,
        role="owner",
        is_active=False,
    )

    try:
        with create_client(
            administrator=administrator,
            companies=[company],
            memberships=[membership],
        ) as client:
            response = client.get(
                "/api/v1/company-context",
                headers={"X-Company-ID": str(company.id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["membership_role"] is None
    assert response.json()["is_platform_superuser"] is True


def test_inactive_membership_does_not_authorize_ordinary_administrator() -> None:
    company = FakeCompany(company_id=uuid4())
    administrator = FakeAdministrator(is_superuser=False)
    membership = FakeMembership(
        company_id=company.id,
        administrator_id=administrator.id,
        role="viewer",
        is_active=False,
    )

    try:
        with create_client(
            administrator=administrator,
            companies=[company],
            memberships=[membership],
        ) as client:
            response = client.get(
                "/api/v1/company-context",
                headers={"X-Company-ID": str(company.id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_matching_settings_path_and_header_reaches_service() -> None:
    company = FakeCompany(company_id=uuid4())

    class EmptySettingService:
        def list_settings(self, **_kwargs: object) -> tuple[list[object], int]:
            return [], 0

    app.dependency_overrides[require_current_administrator] = lambda: (
        FakeAdministrator(is_superuser=True)
    )
    app.dependency_overrides[get_company_service] = lambda: (
        FakeCompanyService([company])
    )
    app.dependency_overrides[get_company_setting_service] = (
        EmptySettingService
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/companies/{company.id}/settings",
                headers={"X-Company-ID": str(company.id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.parametrize(
    ("method", "suffix", "json_body"),
    [
        ("get", "/general/timezone", None),
        ("put", "/general/timezone", {"value": "UTC"}),
        ("delete", "/general/timezone", None),
    ],
)
def test_company_b_operation_is_blocked_in_company_a_context(
    method: str,
    suffix: str,
    json_body: dict[str, str] | None,
) -> None:
    company_a = FakeCompany(company_id=uuid4())
    company_b = FakeCompany(company_id=uuid4())
    setting_service = RecordingSettingService()

    try:
        with create_client(
            administrator=FakeAdministrator(is_superuser=True),
            companies=[company_a, company_b],
            setting_service=setting_service,
        ) as client:
            response = client.request(
                method,
                f"/api/v1/companies/{company_b.id}/settings{suffix}",
                headers={"X-Company-ID": str(company_a.id)},
                json=json_body,
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert setting_service.calls == []
