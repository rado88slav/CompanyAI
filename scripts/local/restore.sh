#!/usr/bin/env bash
# Description: Restore a verified local PostgreSQL backup with explicit confirmation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/local/common.sh
source "$SCRIPT_DIR/common.sh"

print_header "Restore"
require_local_runtime

BACKUP_DIR="${1:-}"
CONFIRM="${2:-}"

if [[ -z "$BACKUP_DIR" || "$CONFIRM" != "RESTORE_COMPANYAI_DATABASE" ]]; then
    echo "Usage: scripts/local/restore.sh <backup-directory> RESTORE_COMPANYAI_DATABASE" >&2
    echo "Restore overwrites the current local database after checksum verification." >&2
    exit 1
fi

if [[ ! -f "$BACKUP_DIR/database.dump" || ! -f "$BACKUP_DIR/checksums.sha256" ]]; then
    echo "Error: Backup directory is missing database.dump or checksums.sha256." >&2
    exit 1
fi

(cd "$BACKUP_DIR" && sha256sum -c checksums.sha256)

cd "$PROJECT_ROOT"

SAFETY_BACKUP="$PROJECT_ROOT/backups/pre-restore-$(date -u +%Y%m%dT%H%M%SZ)"
"$SCRIPT_DIR/backup.sh" "$SAFETY_BACKUP"

echo "Stopping backend and app before restore..."
compose stop app backend

echo "Restoring database..."
compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges' < "$BACKUP_DIR/database.dump"

echo "Starting runtime and verifying health..."
compose up -d --wait --wait-timeout 120
"$SCRIPT_DIR/health-check.sh"
