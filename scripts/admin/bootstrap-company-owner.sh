#!/usr/bin/env bash
# Description: Explicitly create an initial company owner membership after approval.

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${PROJECT_ROOT}"

if [[ $# -ne 4 || "$1" != "--company-id" || "$3" != "--administrator-id" ]]; then
    printf '%s\n' "Usage: $0 --company-id UUID --administrator-id UUID" >&2
    exit 2
fi

docker compose run --rm backend \
    python -m app.cli.bootstrap_company_owner "$@"
