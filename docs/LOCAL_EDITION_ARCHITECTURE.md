# CompanyAI Local Edition Architecture

CompanyAI Local Edition runs on a Windows computer through Docker Desktop and WSL2. The normal target is installation from USB flash drive or external SSD, followed by running the application from the computer's internal SSD.

## Runtime Topology

Traffic flow:

```text
Browser
  -> http://localhost:8080
  -> Nginx reverse proxy and frontend static assets
  -> /api/* proxied to FastAPI backend
  -> PostgreSQL
```

Services in `docker-compose.local.yml`:

- `app`: Nginx runtime image serving the production React build and proxying `/api`.
- `backend`: FastAPI served by Uvicorn without reload, one worker by default for local machines.
- `migrate`: one-shot Alembic migration gate. Backend starts only after this service exits successfully.
- `postgres`: PostgreSQL with named persistent volumes and no host port.

Only `127.0.0.1:8080` is published by default. LAN access can be enabled later by intentionally setting `LOCAL_APP_BIND_ADDRESS=0.0.0.0` in `.env.local`, after firewall and trust decisions are made.

## Reverse Proxy Choice

Nginx is used because it is mature, lightweight, has a small runtime image, serves static SPA assets efficiently, supports SPA fallback cleanly and provides straightforward local reverse proxy behavior.

## Persistence

Critical data uses named Docker volumes:

- `company_ai_local_postgres_data`
- `company_ai_local_backups`
- `company_ai_local_logs`
- `company_ai_local_config`

Normal stop, start, rebuild and image update commands do not delete these volumes. Volume deletion is a separate destructive Docker action and is not part of lifecycle scripts.

Future Windows installer layout:

```text
C:\ProgramData\CompanyAI\
  data\
  backups\
  logs\
  config\
```

The current named-volume strategy keeps data safe while preserving a clear migration path to installer-managed directories.

## Security Boundaries

Local production disables debug by default, does not publish backend or database ports, does not mount the Docker socket, does not run privileged containers and does not create a default administrator. Secrets are supplied through `.env.local`, which must be generated locally and never committed.

Development-only seed commands are not part of `docker-compose.local.yml` and do not run during local production startup.

## Email Sandbox

Email Sandbox is enforced by the backend before provider execution. Local production fails closed when no company policy exists, so no recipient or sender is allowed until a safe company-specific policy is configured. Development mode preserves the existing local dry-run workflow for tests and non-production validation.

## Generic Mailbox Boundary

Generic SMTP/IMAP mailbox setup is part of Provider Connections. It does not
introduce a parallel credential store and does not mount mailbox secrets into
frontend state or local configuration files. Safe connection health is stored
as provider connection metadata; the encrypted password remains in
`provider_credentials`.

Connection tests are administrator actions through the backend API. They use
strict TLS verification and bounded timeouts, perform no send operation and
touch IMAP folders only in read-only mode. Activation reuses the existing
provider connection lifecycle and is refused until an active credential plus
successful SMTP and IMAP tests are present.
