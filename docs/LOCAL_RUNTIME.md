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

If the installation has no administrator, the dashboard shows a setup-required wizard. Complete it once before signing in. The backend rejects setup after an administrator, company or membership exists.

## Administrator Password Recovery

If an existing administrator loses the login password, do not create a new
installation, company or database. Use the local interactive recovery command
against the existing Local Edition backend:

```bash
scripts/local/reset-administrator-password.sh
```

The command uses only `.env.local` and `docker-compose.local.yml`, prompts for
the existing administrator email, shows the selected non-secret account
metadata, requires typing that email again before any change, then reads the
new password twice with hidden `getpass` input. Do not paste the new password
into chat, command arguments, environment variables, tickets or logs.

The reset preserves the administrator identity, company ownership,
memberships, provider connections, mailbox credentials and audit history. It
stores only a new Argon2 password hash and appends a sanitized platform system
audit event. Existing administrator access tokens are stateless in this version
and cannot be centrally revoked; they expire automatically.

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

## Generic SMTP/IMAP Mailbox

Use Provider Connections in the dashboard to add a standards-based mailbox.
The initial defaults are SMTP `465` with SSL/TLS and IMAP `993` with SSL/TLS,
but other standards-compliant SMTP/IMAP hosts can be configured.

Configuration rules:

- Store email address, sender display name, username, hosts, ports, security
  modes, IMAP folder and optional reply-to address as non-secret connection
  configuration.
- Enter the mailbox password only in the masked password field. It is stored
  through encrypted Provider Credentials and is not shown again.
- Run SMTP and IMAP tests separately. The tests authenticate and verify TLS;
  they do not send email and do not modify mailbox messages.
- Activate the connection only after both tests succeed.

Manual live mailbox acceptance remains pending until real credentials are
provided by the operator. Do not use real mailbox passwords in tickets, docs,
terminal transcripts or repository files.

See `docs/MAILBOX_LIVE_ACCEPTANCE.md` for the operator checklist. See
`docs/SINGLE_MESSAGE_TEST.md` for the follow-up approval-gated single-message
simulation checklist and `docs/LIVE_SINGLE_MESSAGE_SMTP_TEST.md` for the
separate one-message LIVE TEST acceptance procedure.

## Email Worker Simulation

Email Operations can run a simulation-only worker preview. It plans what a
future scheduler worker would execute, records a safe audit event and returns
`external_action_taken=false` and `provider_execution_created=false`. It does
not start a live worker process or call SMTP, IMAP, telephony or external
providers.

## AI Agents

The dashboard `/agent` route exposes AI Agents in safe preview mode. The
built-in Email Operations Preview Agent can be created, activated and used for
synthetic preview tasks. It does not send email, read mailbox passwords,
create provider executions, start campaign workers or call external AI
providers. See `docs/AI_AGENT_MANAGER.md`.

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
