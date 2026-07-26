# Troubleshooting CompanyAI Local Edition

## Dashboard Does Not Open

Run:

```bash
scripts/local/status.sh
scripts/local/health-check.sh
```

Confirm Docker Desktop is running and that no other application uses port `8080`.

## Backend Is Not Ready

Readiness depends on PostgreSQL and migrations. Run:

```bash
scripts/local/logs.sh backend migrate
```

Migration errors prevent unsafe startup. The runtime does not recreate or wipe the database automatically.

## Direct Page Refresh Shows an Error

The local Nginx runtime supports SPA fallback for routes such as `/settings`, `/activity`, `/documentation`, `/providers`, `/agent`, `/approvals`, `/campaigns` and `/system-status`. If refresh fails, rebuild and restart:

```bash
scripts/local/restart.sh
```

## Data Persistence

Data is stored in named Docker volumes. Normal stop, start and rebuild commands keep data. Do not remove Docker volumes unless you intend to delete local data.

## Support Bundle

Run:

```bash
scripts/local/diagnose.sh
```

The bundle contains sanitized container status, image metadata, volume metadata and recent logs. It does not contain `.env.local`, passwords, tokens, credential keyrings or provider secrets.

## External Providers

Some future provider features may require internet access and real credentials. Current safety boundaries still prevent real email sends, campaign launches, phone calls and paid actions.
