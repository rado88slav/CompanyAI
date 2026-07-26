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

## Optional Encrypted Configuration Export

To include encrypted local configuration, set a passphrase only for the backup command:

```bash
COMPANYAI_BACKUP_PASSPHRASE=<strong-passphrase> scripts/local/backup.sh
```

The passphrase must not be committed, printed in tickets or stored beside the backup.

## Restore

Restore is explicit and guarded:

```bash
scripts/local/restore.sh <backup-directory> RESTORE_COMPANYAI_DATABASE
```

The restore script verifies checksums and creates a safety backup before overwriting the current database.

If an encrypted config bundle exists, restore does not overwrite `.env.local`.
It decrypts to a support review folder only when both values are set:

```bash
COMPANYAI_BACKUP_PASSPHRASE=<strong-passphrase> \
COMPANYAI_RESTORE_CONFIG_CONFIRMATION=RESTORE_COMPANYAI_CONFIG \
scripts/local/restore.sh <backup-directory> RESTORE_COMPANYAI_DATABASE
```

## Safety

Normal stop, restart, rebuild and update commands preserve data. Data deletion is never part of backup, restore or lifecycle scripts.

Encrypted configuration backup remains a future hardening item.
