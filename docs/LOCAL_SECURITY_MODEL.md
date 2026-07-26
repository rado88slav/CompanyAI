# Local Security Model

CompanyAI Local Edition is locally hosted but treats data as real business data from the first installation.

## Local Runtime

- One public local port: `127.0.0.1:8080`.
- No public PostgreSQL port.
- No public backend port.
- No privileged containers.
- No Docker socket mount.
- No debug or reload process in local production.

## Secrets

Secrets live in `.env.local`, generated on the workstation. Examples contain placeholders only. Secrets must not be committed, printed in diagnostics or exposed in frontend state.

## Email

Outbound email is restricted by the backend Email Sandbox. The UI is not the authority. Every send attempt must be authenticated, company-scoped, approval-gated, allowlisted, quota-limited, duplicate-protected and audited.

## Data

Normal lifecycle commands preserve data. Destructive data removal is not provided by ordinary scripts and must require a separate explicit operation after verified backups.
