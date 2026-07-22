# Architecture Decisions

## 001 — Development environment

Use Windows 10 with WSL2, Ubuntu and Docker Desktop.

## 002 — Project location

Store the project in the WSL Linux filesystem:

    /home/rado/projects/company-ai

Do not develop directly under `/mnt/c/`.

## 003 — Automation

Prefer repeatable Bash scripts instead of long manual command sequences.

Every maintained Bash script should contain a `# Description:` header and be registered by the automatic scripts inventory.

## 004 — Platform structure

Build a modular MVP with:

- dashboard;
- backend API;
- local agent;
- database;
- integrations;
- configuration;
- storage;
- administration.

## 005 — Integration design

External email and phone platforms must be replaceable through configuration and adapters.

Business logic must not depend directly on one external provider.

## 006 — Company separation

Multiple companies must use isolated company context, credentials and data.

Company-owned database records must include a company identifier.

## 007 — Environment secrets

Generate the local `.env` file from `.env.example`.

Generate secure random development secrets automatically.

Never print generated secrets to the terminal and never commit `.env` to Git.

## 008 — PostgreSQL version and storage

Use `postgres:18-alpine` for the current development database.

Mount persistent PostgreSQL storage at:

    /var/lib/postgresql

Expose PostgreSQL on local host port `5433` to avoid common host conflicts.

## 009 — Backend architecture

Use FastAPI with separated layers:

    API routes
    Schemas
    Services
    Repositories
    SQLAlchemy models
    Database session

API routes must not contain direct database business logic.

## 010 — Database migrations

Use Alembic for every database schema change.

Do not create or modify database tables directly from application startup code.

Maintain one linear migration head unless a deliberate migration branch is documented.

## 011 — Company identifiers

Use UUID values as internal Company identifiers.

Use a unique lowercase kebab-case slug as the human-readable stable identifier.

Company names do not need to be unique.

## 012 — Company status

Store a company status and an active flag in the initial Company model.

Supported initial status values:

    active
    inactive

Future lifecycle states require a documented migration.

## 013 — Development company

Use the following temporary Company Context during development:

    Name: CompanyTest
    Slug: company-test

The real company must later be created as a separate Company record.

Development data must not be silently renamed into production data.

## 014 — API versioning

Expose the backend application API under:

    /api/v1

Incompatible API behavior must use a new API version rather than silently breaking existing clients.

## 015 — Phase progression

Non-blocking tasks from an earlier phase may remain in the backlog while foundational work in the next phase begins.

They must remain documented and be completed before MVP stabilization.

## 016 — Company slug updates

The Company UUID is the permanent canonical identifier.

A company slug may be changed through the controlled Company update endpoint when the new slug remains unique.

Internal relations must use the Company UUID rather than the mutable slug.

## 017 — Company settings and secrets

Store non-secret company configuration in the `company_settings` table.

Each setting is identified by:

    company_id
    category
    key

Setting values use PostgreSQL JSONB so the system can store strings, numbers, booleans, lists and structured objects without creating a new column for every integration option.

The combination of company, category and key must remain unique.

Passwords, API keys, access tokens and other secrets must not be stored in `company_settings`.

Secrets will use a separate encrypted credential storage system in a later phase.

## 018 — Administrator authentication

Administrator accounts are global platform identities and do not contain a direct `company_id`.

Future company access permissions must use a separate membership or authorization relationship so one administrator can safely access one or more companies.

Administrator passwords must be stored only as Argon2 hashes.

Plaintext passwords must never be stored, logged, committed or passed through command-line arguments.

Authentication uses short-lived signed JWT access tokens.

JWT validation must explicitly allow only the configured algorithm and require the subject, token type, issued-at time and expiration time.

The signing key is supplied through `APP_SECRET_KEY` and must not be committed to Git.

Health and login endpoints remain public.

Company and Company Settings endpoints require a valid active administrator Bearer token.

## 019 — Active Company Context

Active Company Context is stateless and request-scoped. Clients select it with the `X-Company-ID` HTTP header; it is not stored on the Administrator record.

Only active superusers may select a company context during the MVP. Company memberships and ordinary-administrator company access are deferred to a later authorization task.

Authentication alone does not grant access to every company. Company-owned endpoints must resolve and authorize the selected context before accessing company data.

When a company-owned route also contains `company_id` in its URL, the URL UUID and `X-Company-ID` UUID must match. A mismatch must be rejected before the service performs a read or write.

Service and repository layers must continue to receive `company_id` explicitly and filter company-owned queries by it. Active Company Context must not use process-global or other mutable shared state.
