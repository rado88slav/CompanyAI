#!/usr/bin/env bash
# Description: Stop the Company AI Docker Compose services without deleting containers, networks or data.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"
ENV_FILE="$PROJECT_ROOT/.env"

echo "======================================"
echo " Company AI - Stop"
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

if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "Error: Missing docker-compose.yml." >&2
    exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Error: Missing local .env file." >&2
    exit 1
fi

cd "$PROJECT_ROOT"

echo
echo "Stopping services..."
docker compose stop

echo
echo "Service status:"
docker compose ps -a

echo
echo "Company AI services stopped successfully."
echo "Containers, networks and PostgreSQL data were preserved."