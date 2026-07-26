#!/usr/bin/env bash
# Description: Verify local frontend, reverse proxy, backend and database readiness.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/local/common.sh
source "$SCRIPT_DIR/common.sh"

print_header "Health Check"
require_local_runtime

APP_URL="http://localhost:${LOCAL_APP_PORT:-8080}"

cd "$PROJECT_ROOT"

echo "Container health:"
compose ps

echo
echo "Frontend:"
curl -fsS "$APP_URL/healthz"

echo
echo "Backend through reverse proxy:"
curl -fsS "$APP_URL/api/v1/health"

echo
echo "Readiness through reverse proxy:"
curl -fsS "$APP_URL/api/v1/health/ready"

echo
echo "Migration state:"
compose exec -T backend alembic current
