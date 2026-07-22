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
