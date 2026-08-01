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
    AdministratorNotFoundError,
    AdministratorPasswordPolicyError,
    AdministratorPasswordResetService,
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


class FakePasswordResetSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakePasswordResetRepository:
    def __init__(self, administrator: FakeAdministrator | None) -> None:
        self.administrator = administrator
        self.locked_lookup = False
        self.updated_hash: str | None = None

    def get_by_email(self, email: str, *, for_update: bool = False) -> FakeAdministrator | None:
        if self.administrator is None or email != self.administrator.email:
            return None
        if for_update:
            self.locked_lookup = True
        return self.administrator

    def update_password_hash(self, administrator: FakeAdministrator, *, password_hash: str) -> FakeAdministrator:
        self.updated_hash = password_hash
        administrator.password_hash = password_hash
        return administrator


class FakePasswordResetAudit:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events: list[dict] = []

    def append_platform_system_event(self, **kwargs):
        if self.fail:
            raise ValueError("Audit failed.")
        self.events.append(kwargs)
        return object()


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


def test_local_administrator_password_reset_updates_hash_and_audits_safely() -> None:
    administrator = FakeAdministrator(
        administrator_id=uuid4(),
        email="admin@example.test",
    )
    old_hash = administrator.password_hash
    repository = FakePasswordResetRepository(administrator)
    audit = FakePasswordResetAudit()
    session = FakePasswordResetSession()
    service = AdministratorPasswordResetService(
        repository=repository,  # type: ignore[arg-type]
        audit=audit,  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
    )

    result = service.reset_password(
        email="ADMIN@example.test",
        new_password="New-local-admin-Password-123!",
    )

    assert result.administrator.id == administrator.id
    assert result.session_revocation_supported is False
    assert repository.locked_lookup is True
    assert repository.updated_hash is not None
    assert administrator.password_hash != old_hash
    assert verify_password("New-local-admin-Password-123!", administrator.password_hash)
    assert session.commits == 1
    assert session.rollbacks == 0
    event = audit.events[0]
    assert event["action"] == "administrator.password_reset"
    assert event["resource_type"] == "administrator"
    assert event["resource_id"] == administrator.id
    assert event["details"] == {
        "operation": "local_admin_access_recovery",
        "changed": True,
        "selected_by": "email",
        "target_active": True,
        "target_superuser": True,
        "session_revocation_supported": False,
    }
    serialized_details = repr(event["details"])
    assert "New-local-admin-Password-123!" not in serialized_details
    assert "password" not in serialized_details.lower()
    assert "hash" not in serialized_details.lower()
    assert "token" not in serialized_details.lower()


def test_local_administrator_password_reset_rejects_weak_password_without_write() -> None:
    administrator = FakeAdministrator(administrator_id=uuid4())
    repository = FakePasswordResetRepository(administrator)
    session = FakePasswordResetSession()
    service = AdministratorPasswordResetService(
        repository=repository,  # type: ignore[arg-type]
        audit=FakePasswordResetAudit(),  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
    )

    with pytest.raises(AdministratorPasswordPolicyError):
        service.reset_password(email=administrator.email, new_password="too-short")

    assert repository.updated_hash is None
    assert session.commits == 0
    assert session.rollbacks == 0


def test_local_administrator_password_reset_missing_user_fails_without_write() -> None:
    repository = FakePasswordResetRepository(None)
    session = FakePasswordResetSession()
    service = AdministratorPasswordResetService(
        repository=repository,  # type: ignore[arg-type]
        audit=FakePasswordResetAudit(),  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
    )

    with pytest.raises(AdministratorNotFoundError):
        service.reset_password(email="missing@example.test", new_password="New-local-admin-Password-123!")

    assert repository.updated_hash is None
    assert session.commits == 0
    assert session.rollbacks == 1


def test_local_administrator_password_reset_rolls_back_if_audit_fails() -> None:
    administrator = FakeAdministrator(administrator_id=uuid4())
    repository = FakePasswordResetRepository(administrator)
    session = FakePasswordResetSession()
    service = AdministratorPasswordResetService(
        repository=repository,  # type: ignore[arg-type]
        audit=FakePasswordResetAudit(fail=True),  # type: ignore[arg-type]
        session=session,  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError):
        service.reset_password(email=administrator.email, new_password="New-local-admin-Password-123!")

    assert session.commits == 0
    assert session.rollbacks == 1


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
