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

## First Run

The first administrator is not created by default. The setup status endpoint is read-only, and both the graphical wizard and local bootstrap command close automatically once administrator, company or membership records exist. Passwords are hashed and are never returned or printed.

## Administrator Password Recovery

Local Edition includes an interactive existing-administrator password reset
command for workstation recovery. It must run through `docker-compose.local.yml`
and `.env.local`, select an existing administrator by exact email, hide password
entry, confirm the selected account before writing and use the application
password hashing and policy validation code. It does not create users or
companies, does not touch provider credentials and does not print passwords or
hashes.

The recovery audit event is a platform system event with sanitized metadata
only. Administrator access tokens are currently stateless JWTs, so there is no
refresh/session table to revoke during reset; existing tokens expire according
to their configured lifetime.

## Email

Outbound email is restricted by the backend Email Sandbox. The UI is not the authority. Every send attempt must be authenticated, company-scoped, approval-gated, allowlisted, quota-limited, duplicate-protected and audited.

## Data

Normal lifecycle commands preserve data. Destructive data removal is not provided by ordinary scripts and must require a separate explicit operation after verified backups.
