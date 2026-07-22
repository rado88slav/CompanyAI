"""Tests for administrator authentication and API protection."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import (
    InvalidAccessTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.main import app
from app.schemas.authentication import LoginRequest
from app.services.authentication import (
    AdministratorInactiveError,
    InvalidCredentialsError,
    IssuedAccessToken,
    get_authentication_service,
)

NOW = datetime.now(timezone.utc)
TEST_SECRET_KEY = "a" * 64
TEST_PASSWORD = "A-secure-test-password-123"


class FakeAdministrator:
    """Object compatible with AdministratorResponse validation."""

    def __init__(
        self,
        *,
        administrator_id: UUID,
        email: str = "admin@example.com",
        full_name: str = "Test Administrator",
        is_active: bool = True,
    ) -> None:
        self.id = administrator_id
        self.email = email
        self.full_name = full_name
        self.password_hash = "not-exposed"
        self.is_active = is_active
        self.is_superuser = True
        self.last_login_at: datetime | None = None
        self.created_at = NOW
        self.updated_at = NOW


class FakeAuthenticationService:
    """In-memory authentication service used by API tests."""

    def __init__(
        self,
        *,
        administrator: FakeAdministrator,
        password: str = TEST_PASSWORD,
    ) -> None:
        self.administrator = administrator
        self.password = password
        self.token = "signed-test-access-token"

    def authenticate(
        self,
        login_data: LoginRequest,
    ) -> FakeAdministrator:
        """Validate the fake account credentials."""

        if (
            login_data.email != self.administrator.email
            or login_data.password != self.password
        ):
            raise InvalidCredentialsError

        if not self.administrator.is_active:
            raise AdministratorInactiveError

        self.administrator.last_login_at = datetime.now(
            timezone.utc
        )

        return self.administrator

    def issue_access_token(
        self,
        administrator: FakeAdministrator,
    ) -> IssuedAccessToken:
        """Return a deterministic test token."""

        assert administrator.id == self.administrator.id

        return IssuedAccessToken(
            access_token=self.token,
            expires_in=3600,
        )

    def resolve_access_token(
        self,
        token: str,
    ) -> FakeAdministrator:
        """Resolve the deterministic test token."""

        if token != self.token:
            raise InvalidAccessTokenError

        if not self.administrator.is_active:
            raise AdministratorInactiveError

        return self.administrator


def create_client(
    service: FakeAuthenticationService,
) -> TestClient:
    """Create a client with authentication overridden."""

    app.dependency_overrides[
        get_authentication_service
    ] = lambda: service

    return TestClient(app)


def test_password_hash_round_trip() -> None:
    password_hash = hash_password(TEST_PASSWORD)

    assert password_hash != TEST_PASSWORD
    assert verify_password(TEST_PASSWORD, password_hash)
    assert not verify_password(
        "incorrect-password",
        password_hash,
    )


def test_access_token_round_trip() -> None:
    administrator_id = uuid4()

    token = create_access_token(
        administrator_id,
        secret_key=TEST_SECRET_KEY,
        expires_minutes=60,
    )

    resolved_id = decode_access_token(
        token,
        secret_key=TEST_SECRET_KEY,
    )

    assert resolved_id == administrator_id


def test_tampered_access_token_is_rejected() -> None:
    token = create_access_token(
        uuid4(),
        secret_key=TEST_SECRET_KEY,
        expires_minutes=60,
    )

    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(
            f"{token}tampered",
            secret_key=TEST_SECRET_KEY,
        )


def test_login_returns_bearer_access_token() -> None:
    administrator = FakeAdministrator(
        administrator_id=uuid4(),
    )
    service = FakeAuthenticationService(
        administrator=administrator,
    )

    try:
        with create_client(service) as client:
            response = client.post(
                "/api/v1/auth/login",
                json={
                    "email": "ADMIN@EXAMPLE.COM",
                    "password": TEST_PASSWORD,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "access_token": service.token,
        "token_type": "bearer",
        "expires_in": 3600,
    }
    assert administrator.last_login_at is not None


def test_invalid_login_returns_generic_unauthorized() -> None:
    service = FakeAuthenticationService(
        administrator=FakeAdministrator(
            administrator_id=uuid4(),
        ),
    )

    try:
        with create_client(service) as client:
            response = client.post(
                "/api/v1/auth/login",
                json={
                    "email": "admin@example.com",
                    "password": "wrong-password",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid email or password."
    }
    assert response.headers["www-authenticate"] == "Bearer"


def test_inactive_administrator_cannot_login() -> None:
    service = FakeAuthenticationService(
        administrator=FakeAdministrator(
            administrator_id=uuid4(),
            is_active=False,
        ),
    )

    try:
        with create_client(service) as client:
            response = client.post(
                "/api/v1/auth/login",
                json={
                    "email": "admin@example.com",
                    "password": TEST_PASSWORD,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid email or password."
    }


def test_authenticated_administrator_can_read_profile() -> None:
    administrator = FakeAdministrator(
        administrator_id=uuid4(),
    )
    service = FakeAuthenticationService(
        administrator=administrator,
    )

    try:
        with create_client(service) as client:
            response = client.get(
                "/api/v1/auth/me",
                headers={
                    "Authorization": f"Bearer {service.token}",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == str(administrator.id)
    assert response.json()["email"] == administrator.email
    assert response.json()["is_superuser"] is True


def test_missing_bearer_token_is_rejected() -> None:
    service = FakeAuthenticationService(
        administrator=FakeAdministrator(
            administrator_id=uuid4(),
        ),
    )

    try:
        with create_client(service) as client:
            response = client.get("/api/v1/auth/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json() == {
        "detail": (
            "Valid administrator authentication is required."
        )
    }
    assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_bearer_token_is_rejected() -> None:
    service = FakeAuthenticationService(
        administrator=FakeAdministrator(
            administrator_id=uuid4(),
        ),
    )

    try:
        with create_client(service) as client:
            response = client.get(
                "/api/v1/auth/me",
                headers={
                    "Authorization": "Bearer invalid-token",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


def test_company_api_requires_administrator_authentication() -> None:
    service = FakeAuthenticationService(
        administrator=FakeAdministrator(
            administrator_id=uuid4(),
        ),
    )

    try:
        with create_client(service) as client:
            response = client.get("/api/v1/companies")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
