#!/usr/bin/env bash
# Description: Add Alembic database migrations and Bash migration tools to the Company AI backend.

set -Eeuo pipefail

trap 'echo "Error: Database migration setup failed near line $LINENO." >&2' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
DATABASE_SCRIPTS_DIR="$PROJECT_ROOT/scripts/database"

REQUIREMENTS_FILE="$BACKEND_DIR/requirements.txt"
DOCKERFILE="$BACKEND_DIR/Dockerfile"
ALEMBIC_CONFIG="$BACKEND_DIR/alembic.ini"
MIGRATIONS_DIR="$BACKEND_DIR/migrations"
VERSIONS_DIR="$MIGRATIONS_DIR/versions"

show_usage() {
    cat <<'USAGE'
Usage:
  ./scripts/setup/add-database-migrations.sh

This script:

  - adds Alembic to the backend dependencies;
  - creates the shared SQLAlchemy declarative Base;
  - creates Alembic configuration and migration environment;
  - creates an initial schema baseline migration;
  - updates the backend Docker image;
  - adds migration validation tests;
  - creates Bash tools for applying and generating migrations.

The generated migration tools are:

  ./scripts/database/migrate.sh
  ./scripts/database/migrate.sh current
  ./scripts/database/migrate.sh history

  ./scripts/database/create-migration.sh "migration description"
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
echo " Company AI - Add DB Migrations"
echo "======================================"

REQUIRED_FILES=(
    "$REQUIREMENTS_FILE"
    "$DOCKERFILE"
    "$BACKEND_DIR/app/core/config.py"
    "$BACKEND_DIR/app/db/session.py"
    "$PROJECT_ROOT/docker-compose.yml"
    "$PROJECT_ROOT/.env"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo "Error: Required file is missing: $file" >&2
        exit 1
    fi
done

mkdir -p \
    "$VERSIONS_DIR" \
    "$DATABASE_SCRIPTS_DIR"

echo
echo "Updating backend dependencies..."

cat > "$REQUIREMENTS_FILE" <<'EOF'
fastapi==0.139.1
uvicorn[standard]==0.50.1
SQLAlchemy==2.0.51
psycopg[binary]==3.3.4
alembic==1.16.5
EOF

echo "Creating shared SQLAlchemy declarative base..."

cat > "$BACKEND_DIR/app/db/base.py" <<'EOF'
"""Shared SQLAlchemy declarative model base."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all Company AI database models."""
EOF

cat > "$BACKEND_DIR/app/models/__init__.py" <<'EOF'
"""Company AI database models.

New SQLAlchemy model modules must be imported here so Alembic can discover
their table metadata during automatic migration generation.
"""
EOF

echo "Creating Alembic configuration..."

cat > "$ALEMBIC_CONFIG" <<'EOF'
[alembic]
script_location = %(here)s/migrations
prepend_sys_path = .
path_separator = os
timezone = UTC

# The real URL is loaded securely from the application environment in env.py.
sqlalchemy.url = postgresql+psycopg://placeholder:placeholder@postgres/company_ai

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
EOF

cat > "$MIGRATIONS_DIR/README" <<'EOF'
Company AI database migrations
==============================

Alembic manages all PostgreSQL schema changes for the Company AI platform.

Apply all pending migrations:

    ./scripts/database/migrate.sh

Show the currently applied revision:

    ./scripts/database/migrate.sh current

Show migration history:

    ./scripts/database/migrate.sh history

Generate a migration after changing SQLAlchemy models:

    ./scripts/database/create-migration.sh "describe the schema change"

Always inspect an automatically generated migration before applying it.
Never edit the alembic_version table manually.
EOF

cat > "$MIGRATIONS_DIR/env.py" <<'EOF'
"""Alembic migration environment for Company AI."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import models  # noqa: F401
from app.core.config import get_settings
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Return the PostgreSQL URL without hiding its password."""

    return get_settings().database_url.render_as_string(
        hide_password=False,
    )


def run_migrations_offline() -> None:
    """Run migrations without creating a live database connection."""

    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a live PostgreSQL connection."""

    configuration = config.get_section(
        config.config_ini_section,
    ) or {}

    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
EOF

cat > "$MIGRATIONS_DIR/script.py.mako" <<'EOF'
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Apply this migration."""

    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Reverse this migration."""

    ${downgrades if downgrades else "pass"}
EOF

echo "Creating initial schema baseline migration..."

cat > "$VERSIONS_DIR/0001_initial_schema.py" <<'EOF'
"""Create initial Company AI schema baseline.

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-22
"""

from collections.abc import Sequence
from typing import Union

revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the initial schema baseline.

    No application tables exist yet. Applying this migration establishes
    Alembic schema version tracking in PostgreSQL.
    """

    pass


def downgrade() -> None:
    """Remove the initial schema baseline."""

    pass
EOF

echo "Updating backend Dockerfile..."

cat > "$DOCKERFILE" <<'EOF'
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

COPY --chown=companyai:companyai alembic.ini ./alembic.ini
COPY --chown=companyai:companyai migrations ./migrations
COPY --chown=companyai:companyai app ./app

USER companyai

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

echo "Creating migration validation tests..."

cat > "$BACKEND_DIR/tests/test_migrations.py" <<'EOF'
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

    assert script_directory.get_heads() == ["0001_initial"]


def test_initial_migration_is_available() -> None:
    """The initial migration must be discoverable by Alembic."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )

    revision = script_directory.get_revision("0001_initial")

    assert revision is not None
    assert revision.down_revision is None
EOF

echo "Creating Bash migration runner..."

cat > "$DATABASE_SCRIPTS_DIR/migrate.sh" <<'EOF'
#!/usr/bin/env bash
# Description: Apply or inspect Company AI Alembic database migrations through Docker.

set -Eeuo pipefail

trap 'echo "Error: Migration command failed near line $LINENO." >&2' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"

ACTION="${1:-upgrade}"

show_usage() {
    cat <<'USAGE'
Usage:
  ./scripts/database/migrate.sh
  ./scripts/database/migrate.sh upgrade
  ./scripts/database/migrate.sh current
  ./scripts/database/migrate.sh history

Actions:
  upgrade    Apply every pending migration up to the latest revision.
  current    Show the migration revision currently applied to PostgreSQL.
  history    Show the complete migration revision history.
USAGE
}

case "$ACTION" in
    upgrade)
        ALEMBIC_ARGUMENTS=(upgrade head)
        ;;
    current)
        ALEMBIC_ARGUMENTS=(current --verbose)
        ;;
    history)
        ALEMBIC_ARGUMENTS=(history --verbose)
        ;;
    --help|-h)
        show_usage
        exit 0
        ;;
    *)
        echo "Error: Unsupported migration action: $ACTION" >&2
        show_usage >&2
        exit 1
        ;;
esac

echo "======================================"
echo " Company AI - Database Migration"
echo "======================================"

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: Docker CLI is not available." >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker Engine is not running." >&2
    echo "Start or resume Docker Desktop and try again." >&2
    exit 1
fi

if [[ ! -f "$PROJECT_ROOT/docker-compose.yml" ]]; then
    echo "Error: Missing docker-compose.yml." >&2
    exit 1
fi

if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
    echo "Error: Missing local .env file." >&2
    exit 1
fi

if [[ ! -f "$BACKEND_DIR/alembic.ini" ]]; then
    echo "Error: Missing backend/alembic.ini." >&2
    exit 1
fi

cd "$PROJECT_ROOT"

echo
echo "Validating Docker Compose configuration..."
docker compose config --quiet

echo "Ensuring PostgreSQL is healthy..."
docker compose up \
    -d \
    --wait \
    --wait-timeout 60 \
    postgres

echo
echo "Running Alembic command:"
printf '  alembic'
printf ' %q' "${ALEMBIC_ARGUMENTS[@]}"
printf '\n\n'

docker compose run \
    --rm \
    --no-deps \
    -T \
    -v "$BACKEND_DIR:/app" \
    backend \
    alembic "${ALEMBIC_ARGUMENTS[@]}"

echo
echo "Database migration command completed successfully."
EOF

echo "Creating Bash migration generator..."

cat > "$DATABASE_SCRIPTS_DIR/create-migration.sh" <<'EOF'
#!/usr/bin/env bash
# Description: Generate a new Alembic migration from Company AI SQLAlchemy model changes.

set -Eeuo pipefail

trap 'echo "Error: Migration generation failed near line $LINENO." >&2' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
VERSIONS_DIR="$BACKEND_DIR/migrations/versions"

show_usage() {
    cat <<'USAGE'
Usage:
  ./scripts/database/create-migration.sh "migration description"

Example:
  ./scripts/database/create-migration.sh "create companies table"

The command compares SQLAlchemy model metadata with PostgreSQL and creates
a migration file inside backend/migrations/versions.

Always inspect the generated migration before applying it.
USAGE
}

if (($# != 1)); then
    echo "Error: Provide exactly one quoted migration description." >&2
    show_usage >&2
    exit 1
fi

MIGRATION_MESSAGE="$1"

if [[ -z "${MIGRATION_MESSAGE//[[:space:]]/}" ]]; then
    echo "Error: Migration description cannot be empty." >&2
    exit 1
fi

echo "======================================"
echo " Company AI - Create Migration"
echo "======================================"

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: Docker CLI is not available." >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker Engine is not running." >&2
    exit 1
fi

if [[ ! -f "$PROJECT_ROOT/docker-compose.yml" ]]; then
    echo "Error: Missing docker-compose.yml." >&2
    exit 1
fi

if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
    echo "Error: Missing local .env file." >&2
    exit 1
fi

if [[ ! -f "$BACKEND_DIR/alembic.ini" ]]; then
    echo "Error: Missing backend/alembic.ini." >&2
    exit 1
fi

mkdir -p "$VERSIONS_DIR"

cd "$PROJECT_ROOT"

echo
echo "Validating Docker Compose configuration..."
docker compose config --quiet

echo "Ensuring PostgreSQL is healthy..."
docker compose up \
    -d \
    --wait \
    --wait-timeout 60 \
    postgres

echo
echo "Generating migration:"
echo "  $MIGRATION_MESSAGE"
echo

docker compose run \
    --rm \
    --no-deps \
    -T \
    --user "$(id -u):$(id -g)" \
    -e HOME=/tmp \
    -v "$BACKEND_DIR:/app" \
    backend \
    alembic revision \
    --autogenerate \
    -m "$MIGRATION_MESSAGE"

echo
echo "Migration generated successfully."
echo
echo "Migration files:"

find "$VERSIONS_DIR" \
    -maxdepth 1 \
    -type f \
    -name '*.py' \
    -printf '  - %f\n' \
    | sort

echo
echo "Inspect the new migration before applying it with:"
echo "  ./scripts/database/migrate.sh"
EOF

chmod +x \
    "$DATABASE_SCRIPTS_DIR/migrate.sh" \
    "$DATABASE_SCRIPTS_DIR/create-migration.sh"

echo
echo "Database migration support created successfully."
echo
echo "Generated or updated files:"
echo "  - backend/requirements.txt"
echo "  - backend/Dockerfile"
echo "  - backend/alembic.ini"
echo "  - backend/app/db/base.py"
echo "  - backend/app/models/__init__.py"
echo "  - backend/migrations/README"
echo "  - backend/migrations/env.py"
echo "  - backend/migrations/script.py.mako"
echo "  - backend/migrations/versions/0001_initial_schema.py"
echo "  - backend/tests/test_migrations.py"
echo "  - scripts/database/migrate.sh"
echo "  - scripts/database/create-migration.sh"
echo
echo "The backend image has not been rebuilt yet."
echo "No migration has been applied to PostgreSQL yet."
echo "Next step: validate this generator and the generated configuration."