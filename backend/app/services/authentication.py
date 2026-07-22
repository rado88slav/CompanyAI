"""Application service for administrator authentication."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import (
    InvalidAccessTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db_session
from app.models.administrator import Administrator
from app.repositories.administrator import (
    AdministratorRepository,
)
from app.schemas.authentication import (
    AdministratorCreate,
    LoginRequest,
)

_DUMMY_PASSWORD_HASH = hash_password(
    "company-ai-invalid-password"
)


class AdministratorEmailConflictError(Exception):
    """Raised when an administrator email is already registered."""


class AdministratorNotFoundError(Exception):
    """Raised when an administrator account does not exist."""


class InvalidCredentialsError(Exception):
    """Raised when login credentials are invalid."""


class AdministratorInactiveError(Exception):
    """Raised when an administrator account is inactive."""


@dataclass(frozen=True, slots=True)
class IssuedAccessToken:
    """A signed access token and its lifetime."""

    access_token: str
    expires_in: int


class AuthenticationService:
    """Coordinate administrator creation and authentication."""

    def __init__(
        self,
        repository: AdministratorRepository,
        session: Session,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._session = session
        self._settings = settings

    def create_administrator(
        self,
        administrator_data: AdministratorCreate,
    ) -> Administrator:
        """Create an administrator with a secure password hash."""

        existing_administrator = self._repository.get_by_email(
            administrator_data.email
        )

        if existing_administrator is not None:
            raise AdministratorEmailConflictError(
                "Administrator email already exists."
            )

        password_hash = hash_password(
            administrator_data.password
        )

        try:
            administrator = self._repository.create(
                administrator_data,
                password_hash=password_hash,
            )
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()

            raise AdministratorEmailConflictError(
                "Administrator email already exists."
            ) from exc

        return administrator

    def get_administrator(
        self,
        administrator_id: UUID,
    ) -> Administrator:
        """Return one administrator or raise a domain error."""

        administrator = self._repository.get_by_id(
            administrator_id
        )

        if administrator is None:
            raise AdministratorNotFoundError(
                f"Administrator not found: {administrator_id}"
            )

        return administrator

    def authenticate(
        self,
        login_data: LoginRequest,
    ) -> Administrator:
        """Validate login credentials and record successful access."""

        administrator = self._repository.get_by_email(
            login_data.email
        )

        stored_hash = (
            administrator.password_hash
            if administrator is not None
            else _DUMMY_PASSWORD_HASH
        )

        password_is_valid = verify_password(
            login_data.password,
            stored_hash,
        )

        if administrator is None or not password_is_valid:
            raise InvalidCredentialsError(
                "Invalid administrator credentials."
            )

        if not administrator.is_active:
            raise AdministratorInactiveError(
                "Administrator account is inactive."
            )

        administrator = (
            self._repository.record_successful_login(
                administrator,
                login_time=datetime.now(timezone.utc),
            )
        )

        self._session.commit()

        return administrator

    def issue_access_token(
        self,
        administrator: Administrator,
    ) -> IssuedAccessToken:
        """Create a signed access token for an administrator."""

        expires_minutes = (
            self._settings.access_token_expire_minutes
        )

        token = create_access_token(
            administrator.id,
            secret_key=self._settings.app_secret_key,
            expires_minutes=expires_minutes,
        )

        return IssuedAccessToken(
            access_token=token,
            expires_in=expires_minutes * 60,
        )

    def resolve_access_token(
        self,
        token: str,
    ) -> Administrator:
        """Resolve a trusted token to an active administrator."""

        try:
            administrator_id = decode_access_token(
                token,
                secret_key=self._settings.app_secret_key,
            )
        except InvalidAccessTokenError:
            raise

        administrator = self._repository.get_by_id(
            administrator_id
        )

        if administrator is None:
            raise InvalidAccessTokenError(
                "Access token administrator does not exist."
            )

        if not administrator.is_active:
            raise AdministratorInactiveError(
                "Administrator account is inactive."
            )

        return administrator


def get_authentication_service(
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
    settings: Annotated[
        Settings,
        Depends(get_settings),
    ],
) -> AuthenticationService:
    """Create a request-scoped authentication service."""

    return AuthenticationService(
        repository=AdministratorRepository(session),
        session=session,
        settings=settings,
    )
