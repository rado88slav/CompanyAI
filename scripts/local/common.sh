#!/usr/bin/env bash
# Shared helpers for CompanyAI Local Edition lifecycle scripts.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.local.yml"
ENV_FILE="$PROJECT_ROOT/.env.local"

compose() {
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

require_local_runtime() {
    if ! command -v docker >/dev/null 2>&1; then
        echo "Error: Docker CLI is not available." >&2
        exit 1
    fi

    if ! docker info >/dev/null 2>&1; then
        echo "Error: Docker Engine is not running. Start Docker Desktop and try again." >&2
        exit 1
    fi

    if [[ ! -f "$COMPOSE_FILE" ]]; then
        echo "Error: Missing docker-compose.local.yml." >&2
        exit 1
    fi

    if [[ ! -f "$ENV_FILE" ]]; then
        echo "Error: Missing .env.local." >&2
        echo "Copy .env.local.example to .env.local and generate local secrets before starting." >&2
        exit 1
    fi
}

print_header() {
    echo "======================================"
    echo " CompanyAI Local Edition - $1"
    echo "======================================"
}
