#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

printf '%s\n' "This bootstrap requires migration 0007 and explicit approval."
printf '%s\n' "It is not run by setup or maintenance scripts."
docker compose -f "${PROJECT_ROOT}/docker-compose.yml" exec -T backend \
    python -m app.cli.bootstrap_authorization_safety "$@"
