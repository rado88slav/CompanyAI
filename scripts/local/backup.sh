#!/usr/bin/env bash
# Description: Create a local logical PostgreSQL backup with a checksum manifest.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/local/common.sh
source "$SCRIPT_DIR/common.sh"

print_header "Backup"
require_local_runtime

DESTINATION="${1:-$PROJECT_ROOT/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$DESTINATION/companyai-backup-$STAMP"

mkdir -p "$BACKUP_DIR"

cd "$PROJECT_ROOT"

echo "Creating PostgreSQL logical backup..."
compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-privileges' > "$BACKUP_DIR/database.dump"

{
    echo "backup_version=1"
    echo "created_utc=$STAMP"
    echo "format=postgres-custom"
    echo "contains_database_dump=true"
    echo "contains_env_local=false"
    echo "contains_provider_credentials=false"
} > "$BACKUP_DIR/manifest.txt"

(cd "$BACKUP_DIR" && sha256sum database.dump manifest.txt > checksums.sha256)

echo "Backup created: $BACKUP_DIR"
