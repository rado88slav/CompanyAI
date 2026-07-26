# CompanyAI Local Runtime

## Prerequisites

- Windows with WSL2.
- Docker Desktop with WSL integration enabled.
- A populated `.env.local` based on `.env.local.example`.

Do not commit `.env.local`. It contains local secrets.

## Start

```bash
scripts/local/start.sh
```

The dashboard is available at:

```text
http://localhost:8080
```

## Stop

```bash
scripts/local/stop.sh
```

Stopping does not delete data.

## Restart

```bash
scripts/local/restart.sh
```

## Status

```bash
scripts/local/status.sh
```

## Logs

```bash
scripts/local/logs.sh
```

The logs command redacts common token, password and secret patterns.

## Health Check

```bash
scripts/local/health-check.sh
```

This checks container status, frontend health, backend health through the reverse proxy, readiness and Alembic current revision.

## Diagnostics

```bash
scripts/local/diagnose.sh
```

The diagnostic bundle is saved under `support/`. It contains container status, image metadata, Docker volume metadata and sanitized recent logs. It does not include `.env.local`, credential keyrings, passwords, tokens or provider secrets.

## Backup

```bash
scripts/local/backup.sh
```

Use an external disk destination when needed:

```bash
scripts/local/backup.sh /mnt/e/CompanyAI-Backups
```

## Restore

```bash
scripts/local/restore.sh <backup-directory> RESTORE_COMPANYAI_DATABASE
```

Restore verifies checksums and creates a safety backup first.

## Offline Package

```bash
scripts/local/build-package.sh 0.1.0-beta
```

The package is written under `dist/` and contains Docker images, scripts, wrappers, docs, manifest and checksums. It does not include `.env.local`, generated secrets, Git history or `node_modules`.

## Migration Flow

The `migrate` service runs `alembic upgrade head` before `backend` starts. If migration fails, the backend does not become ready and the application startup fails visibly. The flow never wipes, recreates or downgrades the database.

## Data Safety

Normal lifecycle commands do not delete Docker volumes. Rebuilds update images but keep data. Backups are planned as the next Local Edition milestone.
