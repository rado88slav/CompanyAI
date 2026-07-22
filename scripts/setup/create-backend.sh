#!/usr/bin/env bash
# Description: Generate the initial Company AI FastAPI backend structure and Docker configuration.

set -Eeuo pipefail

trap 'echo "Error: Backend generation failed near line $LINENO." >&2' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"

FORCE=false

show_usage() {
    cat <<'USAGE'
Usage:
  ./scripts/setup/create-backend.sh
  ./scripts/setup/create-backend.sh --force

Options:
  --force    Overwrite files managed by this generator.
  --help     Show this help message.
USAGE
}

while (($# > 0)); do
    case "$1" in
        --force)
            FORCE=true
            ;;
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

    shift
done

echo "======================================"
echo " Company AI - Create Backend"
echo "======================================"

if [[ ! -d "$PROJECT_ROOT" ]]; then
    echo "Error: Project root does not exist: $PROJECT_ROOT" >&2
    exit 1
fi

if [[ ! -f "$PROJECT_ROOT/docker-compose.yml" ]]; then
    echo "Error: docker-compose.yml was not found in the project root." >&2
    exit 1
fi

TARGET_FILES=(
    "$BACKEND_DIR/Dockerfile"
    "$BACKEND_DIR/.dockerignore"
    "$BACKEND_DIR/requirements.txt"
    "$BACKEND_DIR/requirements-dev.txt"
    "$BACKEND_DIR/pytest.ini"
    "$BACKEND_DIR/app/__init__.py"
    "$BACKEND_DIR/app/main.py"
    "$BACKEND_DIR/app/api/__init__.py"
    "$BACKEND_DIR/app/api/router.py"
    "$BACKEND_DIR/app/api/routes/__init__.py"
    "$BACKEND_DIR/app/api/routes/health.py"
    "$BACKEND_DIR/app/core/__init__.py"
    "$BACKEND_DIR/app/core/config.py"
    "$BACKEND_DIR/app/db/__init__.py"
    "$BACKEND_DIR/app/models/__init__.py"
    "$BACKEND_DIR/app/schemas/__init__.py"
    "$BACKEND_DIR/app/services/__init__.py"
    "$BACKEND_DIR/tests/__init__.py"
    "$BACKEND_DIR/tests/test_health.py"
)

if [[ "$FORCE" == false ]]; then
    EXISTING_FILES=()

    for file in "${TARGET_FILES[@]}"; do
        if [[ -e "$file" ]]; then
            EXISTING_FILES+=("$file")
        fi
    done

    if ((${#EXISTING_FILES[@]} > 0)); then
        echo "Error: Backend files already exist." >&2
        echo "No files were overwritten." >&2
        echo >&2

        printf '  - %s\n' "${EXISTING_FILES[@]}" >&2

        echo >&2
        echo "Run with --force only when you intentionally want to replace them:" >&2
        echo "./scripts/setup/create-backend.sh --force" >&2
        exit 1
    fi
fi

echo
echo "Creating backend directories..."

mkdir -p \
    "$BACKEND_DIR/app/api/routes" \
    "$BACKEND_DIR/app/core" \
    "$BACKEND_DIR/app/db" \
    "$BACKEND_DIR/app/models" \
    "$BACKEND_DIR/app/schemas" \
    "$BACKEND_DIR/app/services" \
    "$BACKEND_DIR/tests"

rm -f "$BACKEND_DIR/.gitkeep"

cat > "$BACKEND_DIR/requirements.txt" <<'EOF'
fastapi==0.139.1
uvicorn[standard]==0.50.1
EOF

cat > "$BACKEND_DIR/requirements-dev.txt" <<'EOF'
-r requirements.txt

httpx>=0.27,<1.0
pytest>=8.3,<10.0
EOF

cat > "$BACKEND_DIR/pytest.ini" <<'EOF'
[pytest]
testpaths = tests
pythonpath = .
addopts = -q
EOF

cat > "$BACKEND_DIR/.dockerignore" <<'EOF'
__pycache__/
*.py[cod]
*.log
*.sqlite3
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
tests/
.env
.venv/
venv/
.git/
.gitignore
EOF

cat > "$BACKEND_DIR/Dockerfile" <<'EOF'
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system companyai \
    && useradd \
        --system \
        --gid companyai \
        --home-dir /app \
        companyai

COPY requirements.txt ./requirements.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=companyai:companyai app ./app

USER companyai

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

cat > "$BACKEND_DIR/app/__init__.py" <<'EOF'
"""Company AI backend package."""

__version__ = "0.1.0"
EOF

cat > "$BACKEND_DIR/app/core/__init__.py" <<'EOF'
"""Core backend configuration and shared functionality."""
EOF

cat > "$BACKEND_DIR/app/core/config.py" <<'EOF'
"""Environment-based application configuration."""

from dataclasses import dataclass
from functools import lru_cache
from os import getenv

from app import __version__

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def _read_boolean(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable safely."""

    raw_value = getenv(name)

    if raw_value is None:
        return default

    return raw_value.strip().lower() in _TRUE_VALUES


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
    )
EOF

cat > "$BACKEND_DIR/app/api/__init__.py" <<'EOF'
"""Company AI API package."""
EOF

cat > "$BACKEND_DIR/app/api/routes/__init__.py" <<'EOF'
"""HTTP route modules."""
EOF

cat > "$BACKEND_DIR/app/api/routes/health.py" <<'EOF'
"""Backend health endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings, get_settings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Health endpoint response."""

    status: Literal["ok"]
    service: str
    environment: str
    version: str


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
EOF

cat > "$BACKEND_DIR/app/api/router.py" <<'EOF'
"""Main API router."""

from fastapi import APIRouter

from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
EOF

cat > "$BACKEND_DIR/app/main.py" <<'EOF'
"""Company AI FastAPI application entry point."""

from fastapi import FastAPI
from pydantic import BaseModel

from app.api.router import api_router
from app.core.config import get_settings


class RootResponse(BaseModel):
    """Root endpoint response."""

    service: str
    environment: str
    version: str
    documentation: str


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    application.include_router(
        api_router,
        prefix=settings.api_prefix,
    )

    @application.get(
        "/",
        response_model=RootResponse,
        tags=["system"],
        summary="Show backend information",
    )
    def read_root() -> RootResponse:
        return RootResponse(
            service=settings.app_name,
            environment=settings.app_environment,
            version=settings.app_version,
            documentation="/docs",
        )

    return application


app = create_application()
EOF

cat > "$BACKEND_DIR/app/db/__init__.py" <<'EOF'
"""Database infrastructure package."""
EOF

cat > "$BACKEND_DIR/app/models/__init__.py" <<'EOF'
"""Database model package."""
EOF

cat > "$BACKEND_DIR/app/schemas/__init__.py" <<'EOF'
"""API schema package."""
EOF

cat > "$BACKEND_DIR/app/services/__init__.py" <<'EOF'
"""Application service package."""
EOF

cat > "$BACKEND_DIR/tests/__init__.py" <<'EOF'
"""Company AI backend tests."""
EOF

cat > "$BACKEND_DIR/tests/test_health.py" <<'EOF'
"""Tests for the initial backend endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint() -> None:
    response = client.get("/")

    assert response.status_code == 200

    body = response.json()

    assert body["service"] == "Company AI API"
    assert body["environment"] == "development"
    assert body["version"] == "0.1.0"
    assert body["documentation"] == "/docs"


def test_health_endpoint() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "backend",
        "environment": "development",
        "version": "0.1.0",
    }
EOF

echo
echo "Backend structure created successfully."
echo
echo "Generated files:"

find "$BACKEND_DIR" \
    -type f \
    -not -path '*/__pycache__/*' \
    -printf '  - %P\n' \
    | sort

echo
echo "The backend has not been built or started yet."
echo "Next step: validate this generator, run it and inspect the files."