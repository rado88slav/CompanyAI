#!/usr/bin/env bash
# Description: Display Company AI Docker Compose logs for all services or a selected service.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"
ENV_FILE="$PROJECT_ROOT/.env"

SERVICE_NAME="${1:-}"
TAIL_LINES="${TAIL_LINES:-200}"

echo "======================================"
echo " Company AI - Logs"
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

if ! [[ "$TAIL_LINES" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: TAIL_LINES must be a positive integer." >&2
    exit 1
fi

cd "$PROJECT_ROOT"

if [[ -n "$SERVICE_NAME" ]]; then
    if ! docker compose config --services | grep -Fxq "$SERVICE_NAME"; then
        echo "Error: Unknown Docker Compose service: $SERVICE_NAME" >&2
        echo
        echo "Available services:" >&2
        docker compose config --services >&2
        exit 1
    fi

    echo
    echo "Showing the last $TAIL_LINES log lines for service: $SERVICE_NAME"
    echo "Press Ctrl+C to stop following the logs."
    echo

    docker compose logs \
        --follow \
        --tail "$TAIL_LINES" \
        --timestamps \
        "$SERVICE_NAME"
else
    echo
    echo "Showing the last $TAIL_LINES log lines for all services."
    echo "Press Ctrl+C to stop following the logs."
    echo

    docker compose logs \
        --follow \
        --tail "$TAIL_LINES" \
        --timestamps
fi