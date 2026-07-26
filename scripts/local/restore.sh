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

if [[ -f "$BACKUP_DIR/config.enc" ]]; then
    if [[ "${COMPANYAI_RESTORE_CONFIG_CONFIRMATION:-}" != "RESTORE_COMPANYAI_CONFIG" ]]; then
        echo "Encrypted configuration is present but will not be restored without COMPANYAI_RESTORE_CONFIG_CONFIRMATION=RESTORE_COMPANYAI_CONFIG." >&2
    elif [[ -z "${COMPANYAI_BACKUP_PASSPHRASE:-}" ]]; then
        echo "Error: COMPANYAI_BACKUP_PASSPHRASE is required to restore encrypted configuration." >&2
        exit 1
    else
        if ! command -v openssl >/dev/null 2>&1; then
            echo "Error: openssl is required for encrypted configuration restore." >&2
            exit 1
        fi
        CONFIG_RESTORE_DIR="$PROJECT_ROOT/support/config-restore-$(date -u +%Y%m%dT%H%M%SZ)"
        mkdir -p "$CONFIG_RESTORE_DIR"
        openssl enc -d -aes-256-cbc -pbkdf2 -pass env:COMPANYAI_BACKUP_PASSPHRASE -in "$BACKUP_DIR/config.enc" \
            | tar -C "$CONFIG_RESTORE_DIR" -xf -
        echo "Encrypted configuration was decrypted to $CONFIG_RESTORE_DIR for manual review."
        echo "It was not automatically copied over the active .env.local."
    fi
fi

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
