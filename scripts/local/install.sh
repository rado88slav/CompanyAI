#!/usr/bin/env bash
# Description: Prepare CompanyAI Local Edition configuration and validate prerequisites.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/local/common.sh
source "$SCRIPT_DIR/common.sh"

print_header "Install"

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: Docker Desktop with WSL2 integration is required before installation." >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker Engine is not running. Start Docker Desktop and try again." >&2
    exit 1
fi

if [[ ! -f "$PROJECT_ROOT/.env.local.example" ]]; then
    echo "Error: Missing .env.local.example." >&2
    exit 1
fi

if [[ -f "$ENV_FILE" ]]; then
    echo ".env.local already exists; leaving it unchanged."
else
    cp "$PROJECT_ROOT/.env.local.example" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "Created .env.local from template."
    echo "Replace generated placeholders before starting CompanyAI."
fi

cd "$PROJECT_ROOT"
echo
echo "Validating Compose file..."
compose config --quiet

echo
echo "Installation preparation completed. Start with scripts/local/start.sh after secrets are generated."
