#!/usr/bin/env bash
# Description: Build an offline CompanyAI Local Edition delivery directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/local/common.sh
source "$SCRIPT_DIR/common.sh"

print_header "Build Offline Package"

VERSION="${1:-0.1.0-beta}"
PACKAGE_DIR="$PROJECT_ROOT/dist/companyai-local-$VERSION"
LOCAL_ENV_FILE="${COMPANYAI_LOCAL_ENV_FILE:-$PROJECT_ROOT/.env.local}"

if [[ -e "$PACKAGE_DIR" ]]; then
    echo "Error: Package directory already exists: $PACKAGE_DIR" >&2
    exit 1
fi

cd "$PROJECT_ROOT"

mkdir -p "$PACKAGE_DIR/images" "$PACKAGE_DIR/scripts" "$PACKAGE_DIR/installer" "$PACKAGE_DIR/docs"

if [[ ! -f "$LOCAL_ENV_FILE" ]]; then
    echo "Error: Missing local environment file: $LOCAL_ENV_FILE" >&2
    exit 1
fi

docker compose --env-file "$LOCAL_ENV_FILE" -f docker-compose.local.yml build
docker save company-ai-backend:local company-ai-frontend:local postgres:18-alpine -o "$PACKAGE_DIR/images/companyai-local-images.tar"

cp docker-compose.local.yml .env.local.example "$PACKAGE_DIR/"
cp -R scripts/local "$PACKAGE_DIR/scripts/"
cp -R installer/windows "$PACKAGE_DIR/installer/" 2>/dev/null || true
cp docs/LOCAL_EDITION_ARCHITECTURE.md docs/LOCAL_RUNTIME.md docs/TROUBLESHOOTING_LOCAL.md docs/WINDOWS_INSTALLER_PLAN.md docs/OFFLINE_INSTALLATION.md docs/FIRST_RUN_SETUP.md docs/BACKUP_RESTORE.md docs/OFFLINE_UPDATES.md docs/EMAIL_SANDBOX.md docs/HVAC_WORKSTATION_ACCEPTANCE_TEST.md docs/LOCAL_SECURITY_MODEL.md "$PACKAGE_DIR/docs/"

{
    echo "version=$VERSION"
    echo "created_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "dashboard_url=http://localhost:8080"
    echo "contains_source_control_history=false"
    echo "contains_node_modules=false"
    echo "contains_secrets=false"
} > "$PACKAGE_DIR/manifest.txt"

(cd "$PACKAGE_DIR" && find . -type f -not -name checksums.sha256 -print0 | sort -z | xargs -0 sha256sum > checksums.sha256)

echo "Package created: $PACKAGE_DIR"
