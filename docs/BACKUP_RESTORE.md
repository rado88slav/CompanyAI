# Backup and Restore

CompanyAI Local Edition Beta includes manual local backup and restore scripts.

## Backup

```bash
scripts/local/backup.sh
```

Optional destination:

```bash
scripts/local/backup.sh /mnt/e/CompanyAI-Backups
```

Backups contain a PostgreSQL logical dump, manifest and checksums. They do not include `.env.local`, provider credentials or plaintext secrets.

## Restore

Restore is explicit and guarded:

```bash
scripts/local/restore.sh <backup-directory> RESTORE_COMPANYAI_DATABASE
```

The restore script verifies checksums and creates a safety backup before overwriting the current database.

## Safety

Normal stop, restart, rebuild and update commands preserve data. Data deletion is never part of backup, restore or lifecycle scripts.

Encrypted configuration backup remains a future hardening item.
