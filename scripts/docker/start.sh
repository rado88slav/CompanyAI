#!/usr/bin/env bash
# Description: Start the Company AI Docker Compose environment and display service status.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"
ENV_FILE="$PROJECT_ROOT/.env"

echo "======================================"
echo " Company AI - Start"
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
    echo "Create it with:" >&2
    echo "./scripts/setup/create-env.sh" >&2
    exit 1
fi

cd "$PROJECT_ROOT"

echo
echo "Validating Docker Compose configuration..."
docker compose config --quiet

echo "Starting services..."
docker compose up -d --remove-orphans --wait --wait-timeout 60

echo
echo "Service status:"
docker compose ps

echo
echo "Company AI startup completed."