#!/usr/bin/env bash
# Description: Add SQLAlchemy and PostgreSQL connectivity to the Company AI FastAPI backend.

set -Eeuo pipefail

trap 'echo "Error: Backend database setup failed near line $LINENO." >&2' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"

REQUIREMENTS_FILE="$BACKEND_DIR/requirements.txt"
CONFIG_FILE="$BACKEND_DIR/app/core/config.py"
SESSION_FILE="$BACKEND_DIR/app/db/session.py"
HEALTH_FILE="$BACKEND_DIR/app/api/routes/health.py"
DATABASE_TEST_FILE="$BACKEND_DIR/tests/test_database.py"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"

show_usage() {
    cat <<'USAGE'
Usage:
  ./scripts/setup/add-backend-database.sh

This script:

  - adds SQLAlchemy and Psycopg dependencies;
  - configures a PostgreSQL connection URL;
  - creates the SQLAlchemy engine and session factory;
  - adds a database readiness endpoint;
  - updates the backend Docker healthcheck;
  - creates database endpoint tests.

The script is idempotent and may be run again.
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
echo " Company AI - Add Backend Database"
echo "======================================"

REQUIRED_FILES=(
    "$REQUIREMENTS_FILE"
    "$CONFIG_FILE"
    "$HEALTH_FILE"
    "$COMPOSE_FILE"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo "Error: Required file is missing: $file" >&2
        exit 1
    fi
done

if ! grep -Fq "services:" "$COMPOSE_FILE"; then
    echo "Error: docker-compose.yml does not appear to be valid." >&2
    exit 1
fi

if ! grep -Fq "backend:" "$COMPOSE_FILE"; then
    echo "Error: Backend service was not found in docker-compose.yml." >&2
    exit 1
fi

mkdir -p \
    "$BACKEND_DIR/app/db" \
    "$BACKEND_DIR/tests"

echo
echo "Updating backend dependencies..."

cat > "$REQUIREMENTS_FILE" <<'EOF'
fastapi==0.139.1
uvicorn[standard]==0.50.1
SQLAlchemy==2.0.51
psycopg[binary]==3.3.4
EOF

echo "Creating database-aware application configuration..."

cat > "$CONFIG_FILE" <<'EOF'
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
EOF

echo "Creating SQLAlchemy engine and session factory..."

cat > "$SESSION_FILE" <<'EOF'
"""SQLAlchemy engine and database session management."""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine: Engine = create_engine(
    settings.database_url,
    connect_args={
        "connect_timeout": settings.database_connect_timeout,
    },
    pool_pre_ping=True,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout,
)

SessionFactory = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def get_db_session() -> Generator[Session, None, None]:
    """Provide one database session for a request."""

    session = SessionFactory()

    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
EOF

echo "Adding database readiness endpoint..."

cat > "$HEALTH_FILE" <<'EOF'
"""Backend health and readiness endpoints."""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Basic backend liveness response."""

    status: Literal["ok"]
    service: str
    environment: str
    version: str


class ReadinessResponse(BaseModel):
    """Backend and database readiness response."""

    status: Literal["ok"]
    service: str
    database: Literal["reachable"]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check backend health",
)
def read_health(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    """Return basic backend liveness information."""

    return HealthResponse(
        status="ok",
        service="backend",
        environment=settings.app_environment,
        version=settings.app_version,
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "PostgreSQL is unavailable.",
        },
    },
    summary="Check backend and database readiness",
)
def read_readiness(
    session: Annotated[Session, Depends(get_db_session)],
) -> ReadinessResponse:
    """Verify that the backend can execute a PostgreSQL query."""

    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.exception("PostgreSQL readiness check failed.")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from exc

    return ReadinessResponse(
        status="ok",
        service="backend",
        database="reachable",
    )
EOF

echo "Creating database readiness tests..."

cat > "$DATABASE_TEST_FILE" <<'EOF'
"""Tests for backend database readiness."""

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db_session
from app.main import app


class HealthyDatabaseSession:
    """Minimal successful database session test double."""

    def execute(self, statement: object) -> None:
        del statement


class UnavailableDatabaseSession:
    """Minimal failed database session test double."""

    def execute(self, statement: object) -> None:
        del statement
        raise SQLAlchemyError("Database unavailable")


def override_healthy_database_session(
) -> Generator[HealthyDatabaseSession, None, None]:
    """Provide a successful database session test double."""

    yield HealthyDatabaseSession()


def override_unavailable_database_session(
) -> Generator[UnavailableDatabaseSession, None, None]:
    """Provide an unavailable database session test double."""

    yield UnavailableDatabaseSession()


def test_database_readiness_endpoint() -> None:
    app.dependency_overrides[get_db_session] = (
        override_healthy_database_session
    )

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "backend",
        "database": "reachable",
    }


def test_database_readiness_endpoint_returns_503() -> None:
    app.dependency_overrides[get_db_session] = (
        override_unavailable_database_session
    )

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Database is unavailable.",
    }
EOF

echo "Updating the backend Docker healthcheck..."

OLD_HEALTHCHECK="/api/v1/health', timeout=3"
NEW_HEALTHCHECK="/api/v1/health/ready', timeout=3"

if grep -Fq "$NEW_HEALTHCHECK" "$COMPOSE_FILE"; then
    echo "Docker healthcheck already uses the readiness endpoint."
elif grep -Fq "$OLD_HEALTHCHECK" "$COMPOSE_FILE"; then
    sed -i \
        "s#${OLD_HEALTHCHECK}#${NEW_HEALTHCHECK}#" \
        "$COMPOSE_FILE"
else
    echo "Error: Expected backend healthcheck was not found." >&2
    echo "docker-compose.yml was not modified automatically." >&2
    exit 1
fi

echo
echo "Backend database support added successfully."
echo
echo "Updated files:"
echo "  - backend/requirements.txt"
echo "  - backend/app/core/config.py"
echo "  - backend/app/db/session.py"
echo "  - backend/app/api/routes/health.py"
echo "  - backend/tests/test_database.py"
echo "  - docker-compose.yml"
echo
echo "New readiness endpoint:"
echo "  GET /api/v1/health/ready"
echo
echo "The backend image has not been rebuilt yet."
echo "Next step: validate the Bash and Python syntax."