#!/usr/bin/env bash
# Description: Display the current status of the Company AI Docker Compose services.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"
ENV_FILE="$PROJECT_ROOT/.env"

echo "======================================"
echo " Company AI - Status"
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
echo "Docker Engine:"
docker version --format 'Server version: {{.Server.Version}}'

echo
echo "Compose services:"
docker compose ps -a

echo
echo "Compose images:"
docker compose images

echo
echo "Company AI status check completed."