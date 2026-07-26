#!/usr/bin/env bash
# Description: Create a sanitized local support bundle without secrets.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/local/common.sh
source "$SCRIPT_DIR/common.sh"

print_header "Diagnostics"
require_local_runtime

cd "$PROJECT_ROOT"

SUPPORT_DIR="$PROJECT_ROOT/support"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BUNDLE_DIR="$SUPPORT_DIR/companyai-local-$STAMP"

mkdir -p "$BUNDLE_DIR"

compose ps -a > "$BUNDLE_DIR/containers.txt"
compose images > "$BUNDLE_DIR/images.txt"
docker volume ls --filter name=company_ai_local > "$BUNDLE_DIR/volumes.txt"
compose logs --tail 300 \
    | sed -E 's/(Authorization: Bearer )[A-Za-z0-9._~+\/=-]+/\1[redacted]/g; s/(password=)[^ ]+/\1[redacted]/gi; s/(token=)[^ ]+/\1[redacted]/gi; s/(secret=)[^ ]+/\1[redacted]/gi' \
    > "$BUNDLE_DIR/logs-sanitized.txt"

{
    echo "CompanyAI Local Edition diagnostic bundle"
    echo "Created UTC: $STAMP"
    echo "Contains: container status, image list, Docker volume metadata and sanitized recent logs."
    echo "Does not contain: .env.local, passwords, tokens, credential keyrings or provider secrets."
} > "$BUNDLE_DIR/README.txt"

echo "Created support bundle: $BUNDLE_DIR"
