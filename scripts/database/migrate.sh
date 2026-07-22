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
