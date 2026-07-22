#!/usr/bin/env bash
# Description: Add administrator accounts, secure authentication and protected administration API access.

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
ENV_EXAMPLE="${PROJECT_ROOT}/.env.example"
ENV_FILE="${PROJECT_ROOT}/.env"

printf '%s\n' "======================================"
printf '%s\n' " Company AI - Add Authentication"
printf '%s\n' "======================================"
printf '\n'

printf '%s\n' "Adding authentication dependencies..."

grep -qxF 'pwdlib[argon2]==0.3.0' \
    "${BACKEND_DIR}/requirements.txt" \
|| printf '%s\n' 'pwdlib[argon2]==0.3.0' \
    >> "${BACKEND_DIR}/requirements.txt"

grep -qxF 'PyJWT==2.13.0' \
    "${BACKEND_DIR}/requirements.txt" \
|| printf '%s\n' 'PyJWT==2.13.0' \
    >> "${BACKEND_DIR}/requirements.txt"

printf '%s\n' "Updating environment template..."

if ! grep -q '^ACCESS_TOKEN_EXPIRE_MINUTES=' "${ENV_EXAMPLE}"; then
    sed -i \
        '/^APP_SECRET_KEY=/a ACCESS_TOKEN_EXPIRE_MINUTES=60' \
        "${ENV_EXAMPLE}"
fi

if [[ -f "${ENV_FILE}" ]] &&
    ! grep -q "^ACCESS_TOKEN_EXPIRE_MINUTES=" "${ENV_FILE}"
then
    printf "%s\n" "ACCESS_TOKEN_EXPIRE_MINUTES=60" \
        >> "${ENV_FILE}"
fi

printf '%s\n' "Updating backend Docker environment..."

if ! sed -n \
    '/^  backend:/,/^volumes:/p' \
    "${COMPOSE_FILE}" \
    | grep -q '^      APP_SECRET_KEY:'
then
    sed -i \
        '/^  backend:/,/^volumes:/ {
            /^      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}$/a\
\
      APP_SECRET_KEY: ${APP_SECRET_KEY}
        }' \
        "${COMPOSE_FILE}"
fi

if ! sed -n \
    '/^  backend:/,/^volumes:/p' \
    "${COMPOSE_FILE}" \
    | grep -q '^      CREDENTIAL_ENCRYPTION_KEY:'
then
    sed -i \
        '/^  backend:/,/^volumes:/ {
            /^      APP_SECRET_KEY: ${APP_SECRET_KEY}$/a\
      CREDENTIAL_ENCRYPTION_KEY: ${CREDENTIAL_ENCRYPTION_KEY}
        }' \
        "${COMPOSE_FILE}"
fi

if ! sed -n \
    '/^  backend:/,/^volumes:/p' \
    "${COMPOSE_FILE}" \
    | grep -q '^      ACCESS_TOKEN_EXPIRE_MINUTES:'
then
    sed -i \
        '/^  backend:/,/^volumes:/ {
            /^      CREDENTIAL_ENCRYPTION_KEY: ${CREDENTIAL_ENCRYPTION_KEY}$/a\
      ACCESS_TOKEN_EXPIRE_MINUTES: ${ACCESS_TOKEN_EXPIRE_MINUTES}
        }' \
        "${COMPOSE_FILE}"
fi

printf '%s\n' "Updating application configuration..."

cat > "${BACKEND_DIR}/app/core/config.py" <<'PYTHON'
"""Environment-based application configuration."""

from dataclasses import dataclass
from functools import lru_cache
from os import getenv

from sqlalchemy import URL

from app import __version__

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def _read_boolean(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable safely."""

    raw_value = getenv(name)

    if raw_value is None:
        return default

    return raw_value.strip().lower() in _TRUE_VALUES


def _read_positive_integer(name: str, default: int) -> int:
    """Read and validate a positive integer environment variable."""

    raw_value = getenv(name)

    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {name} must be an integer."
        ) from exc

    if value <= 0:
        raise ValueError(
            f"Environment variable {name} must be greater than zero."
        )

    return value


def _normalize_api_prefix(value: str) -> str:
    """Normalize an API prefix to a stable slash-prefixed format."""

    normalized = value.strip()

    if not normalized:
        return "/api/v1"

    if not normalized.startswith("/"):
        normalized = f"/{normalized}"

    normalized = normalized.rstrip("/")

    return normalized or "/api/v1"


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable application settings."""

    app_name: str
    app_environment: str
    app_version: str
    api_prefix: str
    debug: bool

    app_secret_key: str
    access_token_expire_minutes: int

    postgres_host: str
    postgres_port: int
    postgres_database: str
    postgres_user: str
    postgres_password: str

    database_pool_size: int
    database_max_overflow: int
    database_pool_timeout: int
    database_connect_timeout: int

    @property
    def database_url(self) -> URL:
        """Create a safely encoded SQLAlchemy PostgreSQL URL."""

        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_database,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings(
        app_name=getenv("APP_NAME", "Company AI API"),
        app_environment=getenv("APP_ENV", "development"),
        app_version=getenv("APP_VERSION", __version__),
        api_prefix=_normalize_api_prefix(
            getenv("BACKEND_API_PREFIX", "/api/v1")
        ),
        debug=_read_boolean("BACKEND_DEBUG", default=False),
        app_secret_key=getenv("APP_SECRET_KEY", ""),
        access_token_expire_minutes=_read_positive_integer(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            default=60,
        ),
        postgres_host=getenv("POSTGRES_HOST", "postgres"),
        postgres_port=_read_positive_integer(
            "POSTGRES_PORT",
            default=5432,
        ),
        postgres_database=getenv("POSTGRES_DB", "company_ai"),
        postgres_user=getenv("POSTGRES_USER", "company_ai"),
        postgres_password=getenv("POSTGRES_PASSWORD", ""),
        database_pool_size=_read_positive_integer(
            "DATABASE_POOL_SIZE",
            default=5,
        ),
        database_max_overflow=_read_positive_integer(
            "DATABASE_MAX_OVERFLOW",
            default=10,
        ),
        database_pool_timeout=_read_positive_integer(
            "DATABASE_POOL_TIMEOUT",
            default=30,
        ),
        database_connect_timeout=_read_positive_integer(
            "DATABASE_CONNECT_TIMEOUT",
            default=5,
        ),
    )
PYTHON

printf '%s\n' "Creating Administrator SQLAlchemy model..."

cat > "${BACKEND_DIR}/app/models/administrator.py" <<'PYTHON'
"""Administrator database model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Administrator(Base):
    """A global administrator account for the Company AI platform."""

    __tablename__ = "administrators"
    __table_args__ = (
        CheckConstraint(
            "length(email) >= 3",
            name="ck_administrators_email_not_empty",
        ),
        CheckConstraint(
            "email = lower(email)",
            name="ck_administrators_email_lowercase",
        ),
        CheckConstraint(
            "length(full_name) >= 2",
            name="ck_administrators_full_name_not_empty",
        ),
        UniqueConstraint(
            "email",
            name="uq_administrators_email",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )

    full_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

printf '%s\n' "Registering Administrator metadata..."

cat > "${BACKEND_DIR}/app/models/__init__.py" <<'PYTHON'
"""Company AI database models.

Every SQLAlchemy model must be imported here so Alembic can discover its
metadata during automatic migration generation.
"""

from app.models.administrator import Administrator
from app.models.company import Company, CompanyStatus
from app.models.company_setting import CompanySetting

__all__ = [
    "Administrator",
    "Company",
    "CompanySetting",
    "CompanyStatus",
]
PYTHON

printf '%s\n' "Creating authentication API schemas..."

cat > "${BACKEND_DIR}/app/schemas/authentication.py" <<'PYTHON'
"""Pydantic schemas for administrator authentication."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

_EMAIL_PATTERN = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)


def normalize_email(value: str) -> str:
    """Normalize and validate an administrator email address."""

    normalized = value.strip().lower()

    if not _EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError(
            "A valid email address is required."
        )

    return normalized


class AdministratorCreate(BaseModel):
    """Internal input for creating an administrator."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(
        min_length=3,
        max_length=320,
        examples=["admin@example.com"],
    )

    full_name: str = Field(
        min_length=2,
        max_length=200,
        examples=["Local Administrator"],
    )

    password: str = Field(
        min_length=12,
        max_length=128,
    )

    is_superuser: bool = False

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Normalize the administrator email."""

        return normalize_email(value)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        """Normalize and validate the administrator name."""

        normalized = " ".join(value.split())

        if len(normalized) < 2:
            raise ValueError(
                "Administrator name must contain at least two characters."
            )

        return normalized


class LoginRequest(BaseModel):
    """Administrator login credentials."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(
        min_length=3,
        max_length=320,
    )

    password: str = Field(
        min_length=1,
        max_length=128,
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Normalize the login email."""

        return normalize_email(value)


class AdministratorResponse(BaseModel):
    """Public administrator account information."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """Successful access-token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
PYTHON

printf '%s\n' "Registering authentication schemas..."

cat > "${BACKEND_DIR}/app/schemas/__init__.py" <<'PYTHON'
"""Company AI API schemas."""

from app.schemas.authentication import (
    AdministratorCreate,
    AdministratorResponse,
    LoginRequest,
    TokenResponse,
)
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
    "AdministratorCreate",
    "AdministratorResponse",
    "CompanyCreate",
    "CompanyListResponse",
    "CompanyResponse",
    "CompanySettingListResponse",
    "CompanySettingResponse",
    "CompanySettingUpsert",
    "CompanyUpdate",
    "LoginRequest",
    "TokenResponse",
]
PYTHON

printf '%s\n' "Creating password and token security helpers..."

cat > "${BACKEND_DIR}/app/core/security.py" <<'PYTHON'
"""Password hashing and signed access-token helpers."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"

_password_hash = PasswordHash.recommended()


class SecurityConfigurationError(RuntimeError):
    """Raised when authentication security is not configured safely."""


class InvalidAccessTokenError(ValueError):
    """Raised when an access token cannot be trusted."""


def _validate_secret_key(secret_key: str) -> None:
    """Require a sufficiently long signing secret."""

    if len(secret_key) < 32:
        raise SecurityConfigurationError(
            "APP_SECRET_KEY must contain at least 32 characters."
        )


def hash_password(password: str) -> str:
    """Create an Argon2 password hash."""

    return _password_hash.hash(password)


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:
    """Verify a plaintext password against its stored hash."""

    return _password_hash.verify(
        plain_password,
        password_hash,
    )


def create_access_token(
    administrator_id: UUID,
    *,
    secret_key: str,
    expires_minutes: int,
) -> str:
    """Create a signed administrator access token."""

    _validate_secret_key(secret_key)

    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(
        minutes=expires_minutes,
    )

    payload = {
        "sub": str(administrator_id),
        "type": ACCESS_TOKEN_TYPE,
        "iat": issued_at,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        secret_key,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(
    token: str,
    *,
    secret_key: str,
) -> UUID:
    """Validate an access token and return its administrator UUID."""

    _validate_secret_key(secret_key)

    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[JWT_ALGORITHM],
            options={
                "require": [
                    "sub",
                    "type",
                    "iat",
                    "exp",
                ],
            },
        )

        if payload.get("type") != ACCESS_TOKEN_TYPE:
            raise InvalidAccessTokenError(
                "Unexpected token type."
            )

        subject = payload.get("sub")

        if not isinstance(subject, str):
            raise InvalidAccessTokenError(
                "Token subject is invalid."
            )

        return UUID(subject)
    except (
        jwt.InvalidTokenError,
        ValueError,
        TypeError,
    ) as exc:
        raise InvalidAccessTokenError(
            "Access token is invalid."
        ) from exc
PYTHON

printf '%s\n' "Creating Administrator repository..."

cat > "${BACKEND_DIR}/app/repositories/administrator.py" <<'PYTHON'
"""Database repository for administrator accounts."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.administrator import Administrator
from app.schemas.authentication import AdministratorCreate


class AdministratorRepository:
    """Persist and retrieve administrator accounts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(
        self,
        administrator_id: UUID,
    ) -> Administrator | None:
        """Return one administrator by UUID."""

        return self._session.get(
            Administrator,
            administrator_id,
        )

    def get_by_email(
        self,
        email: str,
    ) -> Administrator | None:
        """Return one administrator by normalized email."""

        statement = select(Administrator).where(
            Administrator.email == email
        )

        return self._session.scalar(statement)

    def create(
        self,
        administrator_data: AdministratorCreate,
        *,
        password_hash: str,
    ) -> Administrator:
        """Create an administrator without committing."""

        administrator = Administrator(
            email=administrator_data.email,
            full_name=administrator_data.full_name,
            password_hash=password_hash,
            is_superuser=administrator_data.is_superuser,
        )

        self._session.add(administrator)
        self._session.flush()
        self._session.refresh(administrator)

        return administrator

    def record_successful_login(
        self,
        administrator: Administrator,
        *,
        login_time: datetime,
    ) -> Administrator:
        """Update the last successful login timestamp."""

        administrator.last_login_at = login_time

        self._session.flush()
        self._session.refresh(administrator)

        return administrator
PYTHON

printf '%s\n' "Registering Administrator repository..."

cat > "${BACKEND_DIR}/app/repositories/__init__.py" <<'PYTHON'
"""Database repository package."""

from app.repositories.administrator import (
    AdministratorRepository,
)
from app.repositories.company import CompanyRepository
from app.repositories.company_setting import (
    CompanySettingRepository,
)

__all__ = [
    "AdministratorRepository",
    "CompanyRepository",
    "CompanySettingRepository",
]
PYTHON

printf '%s\n' "Creating authentication service..."

cat > "${BACKEND_DIR}/app/services/authentication.py" <<'PYTHON'
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
PYTHON

printf '%s\n' "Registering authentication service..."

cat > "${BACKEND_DIR}/app/services/__init__.py" <<'PYTHON'
"""Application service package."""

from app.services.authentication import (
    AdministratorEmailConflictError,
    AdministratorInactiveError,
    AdministratorNotFoundError,
    AuthenticationService,
    InvalidCredentialsError,
    IssuedAccessToken,
    get_authentication_service,
)
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
    "AdministratorEmailConflictError",
    "AdministratorInactiveError",
    "AdministratorNotFoundError",
    "AuthenticationService",
    "CompanyNotFoundError",
    "CompanyService",
    "CompanySettingNotFoundError",
    "CompanySettingService",
    "CompanySlugConflictError",
    "InvalidCredentialsError",
    "IssuedAccessToken",
    "get_authentication_service",
    "get_company_service",
    "get_company_setting_service",
]
PYTHON

printf '%s\n' "Creating authentication API dependency..."

mkdir -p "${BACKEND_DIR}/app/api/dependencies"

cat > "${BACKEND_DIR}/app/api/dependencies/__init__.py" <<'PYTHON'
"""Reusable FastAPI dependencies."""
PYTHON

cat > "${BACKEND_DIR}/app/api/dependencies/authentication.py" <<'PYTHON'
"""FastAPI dependency for authenticated administrators."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.core.security import InvalidAccessTokenError
from app.models.administrator import Administrator
from app.services.authentication import (
    AdministratorInactiveError,
    AuthenticationService,
    get_authentication_service,
)

_bearer_scheme = HTTPBearer(
    auto_error=False,
)


def authentication_required_exception() -> HTTPException:
    """Create the standard authentication-required response."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid administrator authentication is required.",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


def require_current_administrator(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
    service: Annotated[
        AuthenticationService,
        Depends(get_authentication_service),
    ],
) -> Administrator:
    """Return the active administrator represented by a Bearer token."""

    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not credentials.credentials
    ):
        raise authentication_required_exception()

    try:
        return service.resolve_access_token(
            credentials.credentials
        )
    except (
        InvalidAccessTokenError,
        AdministratorInactiveError,
    ) as exc:
        raise authentication_required_exception() from exc
PYTHON

printf '%s\n' "Creating authentication API routes..."

cat > "${BACKEND_DIR}/app/api/routes/authentication.py" <<'PYTHON'
"""HTTP endpoints for administrator authentication."""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from app.api.dependencies.authentication import (
    require_current_administrator,
)
from app.models.administrator import Administrator
from app.schemas.authentication import (
    AdministratorResponse,
    LoginRequest,
    TokenResponse,
)
from app.services.authentication import (
    AdministratorInactiveError,
    AuthenticationService,
    InvalidCredentialsError,
    get_authentication_service,
)

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)


def invalid_login_exception() -> HTTPException:
    """Create a generic login failure without revealing account state."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate an administrator",
)
def login_administrator(
    login_data: LoginRequest,
    service: Annotated[
        AuthenticationService,
        Depends(get_authentication_service),
    ],
) -> TokenResponse:
    """Validate credentials and issue a signed access token."""

    try:
        administrator = service.authenticate(login_data)
    except (
        InvalidCredentialsError,
        AdministratorInactiveError,
    ) as exc:
        raise invalid_login_exception() from exc

    issued_token = service.issue_access_token(
        administrator
    )

    return TokenResponse(
        access_token=issued_token.access_token,
        expires_in=issued_token.expires_in,
    )


@router.get(
    "/me",
    response_model=AdministratorResponse,
    summary="Get the current administrator",
)
def get_current_administrator(
    administrator: Annotated[
        Administrator,
        Depends(require_current_administrator),
    ],
) -> AdministratorResponse:
    """Return the authenticated administrator account."""

    return AdministratorResponse.model_validate(
        administrator
    )
PYTHON

printf '%s\n' "Registering authentication API router..."

cat > "${BACKEND_DIR}/app/api/router.py" <<'PYTHON'
"""Main API router."""

from fastapi import APIRouter

from app.api.routes.authentication import (
    router as authentication_router,
)
from app.api.routes.companies import router as companies_router
from app.api.routes.company_settings import (
    router as company_settings_router,
)
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(authentication_router)
api_router.include_router(companies_router)
api_router.include_router(company_settings_router)
PYTHON

printf '%s\n' "Protecting Company API routes..."

if ! grep -q \
    'from app.api.dependencies.authentication import' \
    "${BACKEND_DIR}/app/api/routes/companies.py"
then
    sed -i \
        '/^from app.schemas.company import (/i\
from app.api.dependencies.authentication import (\
    require_current_administrator,\
)\
' \
        "${BACKEND_DIR}/app/api/routes/companies.py"
fi

if ! grep -q \
    'dependencies=\[Depends(require_current_administrator)\]' \
    "${BACKEND_DIR}/app/api/routes/companies.py"
then
    sed -i \
        '/^    tags=\["companies"\],$/a\
    dependencies=[Depends(require_current_administrator)],' \
        "${BACKEND_DIR}/app/api/routes/companies.py"
fi

printf '%s\n' "Protecting Company Settings API routes..."

if ! grep -q \
    'from app.api.dependencies.authentication import' \
    "${BACKEND_DIR}/app/api/routes/company_settings.py"
then
    sed -i \
        '/^from app.schemas.company_setting import (/i\
from app.api.dependencies.authentication import (\
    require_current_administrator,\
)\
' \
        "${BACKEND_DIR}/app/api/routes/company_settings.py"
fi

if ! grep -q \
    'dependencies=\[Depends(require_current_administrator)\]' \
    "${BACKEND_DIR}/app/api/routes/company_settings.py"
then
    sed -i \
        '/^    tags=\["company-settings"\],$/a\
    dependencies=[Depends(require_current_administrator)],' \
        "${BACKEND_DIR}/app/api/routes/company_settings.py"
fi

printf '%s\n' "Creating Administrator database migration..."

cat > "${BACKEND_DIR}/migrations/versions/0004_create_administrators_table.py" <<'PYTHON'
"""Create administrators table.

Revision ID: 0004_administrators
Revises: 0003_company_settings
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_administrators"
down_revision: str | None = "0003_company_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the administrators table."""

    op.create_table(
        "administrators",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "email",
            sa.String(length=320),
            nullable=False,
        ),
        sa.Column(
            "full_name",
            sa.String(length=200),
            nullable=False,
        ),
        sa.Column(
            "password_hash",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "is_superuser",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(email) >= 3",
            name="ck_administrators_email_not_empty",
        ),
        sa.CheckConstraint(
            "email = lower(email)",
            name="ck_administrators_email_lowercase",
        ),
        sa.CheckConstraint(
            "length(full_name) >= 2",
            name="ck_administrators_full_name_not_empty",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "email",
            name="uq_administrators_email",
        ),
    )


def downgrade() -> None:
    """Remove the administrators table."""

    op.drop_table("administrators")
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
        "0004_administrators"
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


def test_administrator_migration_follows_settings_revision() -> None:
    """Administrator storage must follow company settings."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )

    revision = script_directory.get_revision(
        "0004_administrators"
    )

    assert revision is not None
    assert revision.down_revision == "0003_company_settings"
PYTHON

printf '%s\n' "Adapting existing Company tests for protected routes..."

if ! grep -q \
    'from app.api.dependencies.authentication import' \
    "${BACKEND_DIR}/tests/test_company_domain.py"
then
    sed -i \
        '/^from app.main import app$/i\
from app.api.dependencies.authentication import (\
    require_current_administrator,\
)\
' \
        "${BACKEND_DIR}/tests/test_company_domain.py"
fi

if ! grep -q \
    'Authentication behavior is tested separately' \
    "${BACKEND_DIR}/tests/test_company_domain.py"
then
    sed -i \
        '/"""Create a client with the Company service overridden."""/a\
\
    # Authentication behavior is tested separately.\
    app.dependency_overrides[\
        require_current_administrator\
    ] = lambda: object()' \
        "${BACKEND_DIR}/tests/test_company_domain.py"
fi

printf '%s\n' "Adapting existing Company Settings tests..."

if ! grep -q \
    'from app.api.dependencies.authentication import' \
    "${BACKEND_DIR}/tests/test_company_settings.py"
then
    sed -i \
        '/^from app.main import app$/i\
from app.api.dependencies.authentication import (\
    require_current_administrator,\
)\
' \
        "${BACKEND_DIR}/tests/test_company_settings.py"
fi

if ! grep -q \
    'Authentication behavior is tested separately' \
    "${BACKEND_DIR}/tests/test_company_settings.py"
then
    sed -i \
        '/"""Create a client with the setting service overridden."""/a\
\
    # Authentication behavior is tested separately.\
    app.dependency_overrides[\
        require_current_administrator\
    ] = lambda: object()' \
        "${BACKEND_DIR}/tests/test_company_settings.py"
fi

printf '%s\n' "Creating authentication and security tests..."

cat > "${BACKEND_DIR}/tests/test_authentication.py" <<'PYTHON'
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
PYTHON

printf '%s\n' "Creating local administrator CLI..."

mkdir -p "${BACKEND_DIR}/app/cli"
mkdir -p "${PROJECT_ROOT}/scripts/admin"

cat > "${BACKEND_DIR}/app/cli/__init__.py" <<'PYTHON'
"""Command-line utilities for Company AI administration."""
PYTHON

cat > "${BACKEND_DIR}/app/cli/create_administrator.py" <<'PYTHON'
"""Create a local administrator from data received through stdin."""

import sys

from pydantic import ValidationError

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.repositories.administrator import (
    AdministratorRepository,
)
from app.schemas.authentication import AdministratorCreate
from app.services.authentication import (
    AdministratorEmailConflictError,
    AuthenticationService,
)


def read_input() -> AdministratorCreate:
    """Read administrator fields without exposing the password."""

    input_lines = sys.stdin.read().splitlines()

    if len(input_lines) != 4:
        raise ValueError(
            "Expected email, full name, password and superuser flag."
        )

    email, full_name, password, superuser_value = input_lines

    return AdministratorCreate(
        email=email,
        full_name=full_name,
        password=password,
        is_superuser=(
            superuser_value.strip().lower() == "true"
        ),
    )


def main() -> int:
    """Create one administrator and return a process exit code."""

    try:
        administrator_data = read_input()
    except (ValueError, ValidationError):
        print(
            (
                "Invalid administrator data. "
                "Use a valid email, a name of at least two "
                "characters and a password of at least "
                "twelve characters."
            ),
            file=sys.stderr,
        )
        return 2

    with SessionFactory() as session:
        service = AuthenticationService(
            repository=AdministratorRepository(session),
            session=session,
            settings=get_settings(),
        )

        try:
            administrator = service.create_administrator(
                administrator_data
            )
        except AdministratorEmailConflictError:
            print(
                (
                    "An administrator with this email "
                    "already exists."
                ),
                file=sys.stderr,
            )
            return 3

    print("Administrator created successfully.")
    print(f"ID: {administrator.id}")
    print(f"Email: {administrator.email}")
    print(f"Full name: {administrator.full_name}")
    print(f"Superuser: {administrator.is_superuser}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PYTHON

printf '%s\n' "Creating local administrator Bash script..."

cat > "${PROJECT_ROOT}/scripts/admin/create-local-administrator.sh" <<'BASH'
#!/usr/bin/env bash
# Description: Create a local administrator without exposing the password in shell history.

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${PROJECT_ROOT}"

printf '%s\n' "======================================"
printf '%s\n' " Company AI - Create Administrator"
printf '%s\n' "======================================"
printf '\n'

docker compose config --quiet
docker compose up -d --wait postgres

read -r -p "Administrator email: " administrator_email
read -r -p "Administrator full name: " administrator_full_name

printf '%s' "Password (minimum 12 characters): "
read -r -s administrator_password
printf '\n'

printf '%s' "Confirm password: "
read -r -s administrator_password_confirmation
printf '\n'

if [[ "${administrator_password}" != \
      "${administrator_password_confirmation}" ]]
then
    unset administrator_password
    unset administrator_password_confirmation

    printf '%s\n' "Error: Passwords do not match." >&2
    exit 1
fi

if (( ${#administrator_password} < 12 )); then
    unset administrator_password
    unset administrator_password_confirmation

    printf '%s\n' \
        "Error: Password must contain at least 12 characters." \
        >&2
    exit 1
fi

printf '\n%s\n' \
    "Creating the first local administrator as a superuser..."

printf '%s\n%s\n%s\n%s\n' \
    "${administrator_email}" \
    "${administrator_full_name}" \
    "${administrator_password}" \
    "true" \
| docker compose run --rm -T backend \
    python -m app.cli.create_administrator

unset administrator_password
unset administrator_password_confirmation

printf '\n%s\n' "Local administrator command completed."
BASH

chmod +x \
    "${PROJECT_ROOT}/scripts/admin/create-local-administrator.sh"

printf '%s\n' "Validating Docker Compose configuration..."

(
    cd "${PROJECT_ROOT}"
    docker compose config --quiet
)

printf '\n%s\n' "Authentication foundation generated successfully."
printf '%s\n' "Generated or updated files:"
printf '%s\n' "  - backend/requirements.txt"
printf '%s\n' "  - backend/app/core/config.py"
printf '%s\n' "  - backend/app/core/security.py"
printf '%s\n' "  - backend/app/models/administrator.py"
printf '%s\n' "  - backend/app/models/__init__.py"
printf '%s\n' "  - backend/app/schemas/authentication.py"
printf '%s\n' "  - backend/app/schemas/__init__.py"
printf '%s\n' "  - backend/app/repositories/administrator.py"
printf '%s\n' "  - backend/app/repositories/__init__.py"
printf '%s\n' "  - backend/app/services/authentication.py"
printf '%s\n' "  - backend/app/services/__init__.py"
printf '%s\n' "  - backend/app/api/dependencies/authentication.py"
printf '%s\n' "  - backend/app/api/routes/authentication.py"
printf '%s\n' "  - backend/app/api/routes/companies.py"
printf '%s\n' "  - backend/app/api/routes/company_settings.py"
printf '%s\n' "  - backend/app/api/router.py"
printf '%s\n' "  - backend/app/cli/create_administrator.py"
printf '%s\n' "  - backend/migrations/versions/0004_create_administrators_table.py"
printf '%s\n' "  - backend/tests/test_authentication.py"
printf '%s\n' "  - backend/tests/test_company_domain.py"
printf '%s\n' "  - backend/tests/test_company_settings.py"
printf '%s\n' "  - backend/tests/test_migrations.py"
printf '%s\n' "  - scripts/admin/create-local-administrator.sh"
printf '%s\n' "  - docker-compose.yml"
printf '%s\n' "  - .env.example"
printf '%s\n' "  - .env, when present"

printf '\n%s\n' "No migration has been applied yet."
printf '%s\n' "No administrator has been created yet."
printf '%s\n' "The backend image has not been rebuilt yet."
printf '%s\n' "Expected automated verification: 39 passed."
