#!/usr/bin/env bash
# Description: Update project progress, tasks, architecture decisions and inventory.

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ADMIN_DIR="${PROJECT_ROOT}/project-admin"

printf '%s\n' "======================================"
printf '%s\n' " Company AI - Update Project Status"
printf '%s\n' "======================================"
printf '\n'

mkdir -p "${ADMIN_DIR}"

cat > "${ADMIN_DIR}/progress.md" <<'EOF'
# Project Progress

## Current Phase

**Phase 3 — Company and Administration Core: In Progress**

The Company domain, Company Settings, administrator authentication, Active Company Context and Audit Logging foundations are operational.

Some non-blocking work from Phase 1 and Phase 2 remains in the backlog, including the initial agent container, dashboard container, structured logging and additional system endpoints.

---

## Phase Status

### Phase 0 — Project Foundation

**Completed**

### Phase 1 — Docker and Database Foundation

**Partially completed**

Completed:

- secure environment configuration;
- PostgreSQL container;
- persistent PostgreSQL storage;
- database health check;
- backend container;
- internal Docker network;
- service startup dependencies;
- Docker start, stop, restart, status and log scripts.

Remaining:

- initial agent container;
- initial dashboard container;
- development reset script;
- complete Docker installation documentation.

### Phase 2 — Backend API Foundation

**Core foundation operational**

Completed:

- FastAPI backend;
- API versioning under `/api/v1`;
- environment-based application settings;
- SQLAlchemy integration;
- PostgreSQL connectivity;
- Alembic migration framework;
- health endpoint;
- database readiness endpoint;
- automated tests;
- Docker backend health check.

Remaining:

- structured logging;
- unified API error response format;
- system information endpoint;
- additional backend documentation.

### Phase 3 — Company and Administration Core

**In progress**

Completed:

- `Company` SQLAlchemy model;
- UUID company identifiers;
- unique company slugs;
- active and inactive company status;
- Company API schemas;
- Company repository;
- Company service;
- company creation endpoint;
- company list endpoint;
- company read-by-ID endpoint;
- company partial update endpoint;
- company activation endpoint;
- company deactivation endpoint;
- synchronized `status` and `is_active` changes;
- empty and null update validation;
- duplicate slug conflict handling;
- missing company handling;
- Alembic migration `0002_companies`;
- migration validation tests;
- Company API tests;
- development company `CompanyTest` stored in PostgreSQL;
- `CompanySetting` SQLAlchemy model;
- JSONB setting values;
- settings grouped by company, category and key;
- unique company/category/key combinations;
- Company Settings repository and service;
- Company Settings API schemas and routes;
- setting upsert, list, read and delete operations;
- company ownership validation;
- cross-company isolation tests;
- Alembic migration `0003_company_settings`;
- Company Settings API verified against PostgreSQL;
- `Administrator` SQLAlchemy model;
- globally unique lowercase administrator emails;
- Argon2 password hashing;
- signed JWT access tokens;
- administrator login endpoint;
- authenticated administrator profile endpoint;
- Bearer authentication dependency;
- protected Company and Company Settings APIs;
- inactive administrator rejection;
- generic login failure responses;
- successful login timestamp tracking;
- local superuser creation CLI;
- local superuser stored in PostgreSQL;
- Alembic migration `0004_administrators`;
- authentication and security tests;
- Authentication API verified against PostgreSQL.
- stateless request-scoped Active Company Context through `X-Company-ID`;
- superuser-only company context selection for the MVP;
- active company validation and typed request context;
- company context discovery endpoint;
- Company Settings path and header context enforcement;
- cross-company read, write and delete isolation tests.
- append-only `AuditLog` model and repository;
- atomic company mutation and audit persistence;
- normalized company audit actions and safe JSONB details;
- company activity endpoint protected by Active Company Context;
- Alembic migration `0005_audit_logs` applied to local PostgreSQL;
- audit table, constraints, indexes and `ON DELETE RESTRICT` foreign keys verified against PostgreSQL;
- no historical audit backfill performed;
- authenticated Audit Logging API flow verified end-to-end;
- no-op activation of `CompanyTest` returned HTTP 200 and preserved its active state;
- company activity retrieval returned HTTP 200;
- exactly one approved `company.activated` verification event persisted with company scope, administrator actor and `changed: false`;
- verification event company and resource IDs match `CompanyTest`, and its actor ID matches the authenticated local administrator;
- audit logging, rollback and activity API tests;
- complete Audit Logging backend suite verification;

Remaining:

- repeatable development seed automation.

---

## Automated Verification

Latest backend verification:

    76 passed, 1 warning

The warning is a non-blocking Starlette `TestClient` deprecation warning.

Alembic migration chain:

    <base> -> 0001_initial -> 0002_companies -> 0003_company_settings -> 0004_administrators -> 0005_audit_logs (head, applied locally)

---

## Current API

    GET  /
    GET  /api/v1/health
    GET  /api/v1/health/ready
    POST /api/v1/auth/login
    GET  /api/v1/auth/me
    GET  /api/v1/company-context
    POST /api/v1/companies
    GET  /api/v1/companies
    GET   /api/v1/companies/{company_id}
    PATCH /api/v1/companies/{company_id}
    POST  /api/v1/companies/{company_id}/activate
    POST  /api/v1/companies/{company_id}/deactivate
    GET   /api/v1/companies/{company_id}/activity
    PUT    /api/v1/companies/{company_id}/settings/{category}/{key}
    GET    /api/v1/companies/{company_id}/settings
    GET    /api/v1/companies/{company_id}/settings/{category}/{key}
    DELETE /api/v1/companies/{company_id}/settings/{category}/{key}

Company management routes require a valid administrator Bearer token.

The Company Context endpoint and Company Settings routes also require `X-Company-ID`. Only active superusers may select a company context, and Company Settings URL company IDs must match the header context.

Company activity requires the same Active Company Context protection. Inactive company activity is not viewable through this endpoint in the current version.

---

## Current Docker Services

### PostgreSQL

- image: `postgres:18-alpine`;
- internal port: `5432`;
- local host port: `5433`;
- persistent volume enabled;
- health check operational.

### Backend

- image: `company-ai-backend:dev`;
- framework: FastAPI;
- local host port: `8000`;
- PostgreSQL readiness check operational;
- container health check operational.

---

## Current Development Company

    ID: 0138bfbe-80af-4304-ad91-14d1914a9869
    Name: CompanyTest
    Slug: company-test
    Status: active

`CompanyTest` is temporary development data.

The real company will later be created as a separate Company Context without changing the database architecture.

---

## Current System Status

- WSL2: operational
- Ubuntu: operational
- Docker Desktop: operational
- Docker Engine: operational
- Docker Compose: operational
- PostgreSQL: healthy
- FastAPI backend: healthy
- Alembic migrations: operational
- Company API: operational
- Company Settings API: operational
- Administrator authentication: operational
- Active Company Context: operational
- Company Settings context isolation: operational
- Audit Logging: operational
- Audit migration `0005_audit_logs`: applied locally
- Audit schema persistence: verified against PostgreSQL
- Audit event persistence and company activity retrieval: verified end-to-end
- Audit history: one explicitly approved no-op verification event; no historical backfill
- Bearer-protected administration routes: operational
- Company persistence: verified
- Company Settings persistence: verified
- Automated tests: passing
- Git repository: operational

---

## Next Work

Continue Phase 3 with:

1. development seed automation.

---

## Last Updated

2026-07-22
EOF

cat > "${ADMIN_DIR}/todo.md" <<'EOF'
# Project To-Do

## Current Phase

**Phase 3 — Company and Administration Core**

---

## Immediate Tasks

### 1. Complete the Company Domain Foundation

- [x] Create the Company database model.
- [x] Create Company API schemas.
- [x] Create the Company repository.
- [x] Create the Company service.
- [x] Create Company API routes.
- [x] Create migration `0002_companies`.
- [x] Apply the migration to PostgreSQL.
- [x] Create Company API tests.
- [x] Run all automated tests.
- [x] Build the updated backend image.
- [x] Restart and verify Docker services.
- [x] Create the `CompanyTest` development company.
- [x] Verify list and read-by-ID endpoints.
- [x] Update project administration documents.
- [x] Update project inventory.
- [x] Review staged files for secrets.
- [x] Commit the Company domain foundation.

### 2. Company Management

- [x] Add a company update schema.
- [x] Add a company update repository operation.
- [x] Add a company update service operation.
- [x] Add `PATCH /api/v1/companies/{company_id}`.
- [x] Add company activation.
- [x] Add company deactivation.
- [x] Add tests for updates and status changes.
- [x] Allow controlled slug changes while UUID remains the canonical identifier.

### 3. Company Settings

- [x] Define the `CompanySetting` model.
- [x] Define supported setting categories.
- [x] Create a migration for company settings.
- [x] Create settings repository and service layers.
- [x] Create settings API endpoints.
- [x] Ensure every setting belongs to exactly one company.
- [x] Add company isolation tests.

### 4. Administrator Foundation

- [x] Define the administrator or user model.
- [x] Store passwords using a secure password hash.
- [x] Create one local administrator account.
- [x] Add a login endpoint.
- [x] Add authenticated session or token handling.
- [x] Protect administration endpoints.
- [x] Add authentication tests.

### 5. Active Company Context

- [x] Define `X-Company-ID` as the stateless company selector.
- [x] Reject missing or invalid company context.
- [x] Restrict context selection to active superusers.
- [x] Ensure company-owned records contain `company_id`.
- [x] Prevent cross-company reads.
- [x] Prevent cross-company writes and deletes.
- [x] Add two-company isolation tests.
- [x] Prepare the future dashboard company selector.

### 6. Audit Logging

- [x] Define the append-only `AuditLog` model.
- [x] Record company creation.
- [x] Record company updates.
- [x] Record activation and deactivation commands.
- [x] Record administrator actors explicitly.
- [x] Create a company activity endpoint.
- [x] Add audit log and transaction rollback tests.

### 7. Development Seed Data

- [ ] Create a repeatable seed script.
- [ ] Preserve the `CompanyTest` development convention.
- [ ] Make seed execution idempotent.
- [ ] Prevent development seeds from running in production.
- [ ] Document seed usage.

---

## Remaining Phase 1 Work

- [ ] Create the initial agent container.
- [ ] Create the initial dashboard container.
- [ ] Add agent health information.
- [ ] Add dashboard health information.
- [ ] Create `scripts/docker/reset-dev.sh`.
- [ ] Complete Docker startup documentation.

---

## Remaining Phase 2 Work

- [ ] Add structured backend logging.
- [ ] Add a unified API error response format.
- [ ] Add `GET /api/v1/system/info`.
- [ ] Review health endpoint naming against the roadmap.
- [ ] Document backend module conventions.
- [ ] Document migration creation and execution.

---

## Phase 3 Completion Criteria

Phase 3 is complete when:

- [ ] At least two test companies can exist.
- [x] Companies can be created, read, updated and activated.
- [x] A local administrator can authenticate.
- [x] Company settings are stored separately.
- [x] Current company-owned records are isolated.
- [x] Cross-company access tests pass.
- [x] Company changes create audit records.
- [ ] The active company can be identified by the dashboard.
- [ ] Development seed data can be created safely.
- [ ] Documentation and inventory are current.
- [ ] No secrets are committed.
- [ ] Git working tree is clean.

---

## Later Phases

- [ ] Phase 4 — Dashboard Foundation
- [ ] Phase 5 — Task and Agent Runtime
- [ ] Phase 6 — AI Provider Integration
- [ ] Phase 7 — Approval and Permission System
- [ ] Phase 8 — Integration Framework
- [ ] Phase 9 — Email Platform Management
- [ ] Phase 10 — Phone Platform Management
- [ ] Phase 11 — Automation Engine
- [ ] Phase 12 — Backup, Restore and Portability
- [ ] Phase 13 — MVP Stabilization

---

## Explicitly Postponed

The following features must not delay the MVP:

- lead scraping;
- email and phone discovery;
- document knowledge base;
- vector database;
- browser automation;
- local Ollama models;
- CRM synchronization;
- visual workflow builder;
- Kubernetes;
- unrestricted autonomous actions.

---

## Last Updated

2026-07-22
EOF

cat > "${ADMIN_DIR}/decisions.md" <<'EOF'
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

## 020 — Audit Logging

Audit logs use an append-only application contract. Audit repositories and APIs do not expose update or delete operations, and audit records do not contain an `updated_at` field.

Company mutations and their audit records use the same request-scoped SQLAlchemy session and are committed exactly once by the Company service. A mutation or audit failure rolls back the complete transaction.

Actions use normalized lowercase dotted names. The initial actions are `company.created`, `company.updated`, `company.activated` and `company.deactivated`.

Audit details contain only explicit non-secret allowlisted JSON objects. Passwords, hashes, tokens, keys, credentials, request headers, unrestricted request payloads and secret setting values must never be stored.

Company activity is isolated through Active Company Context. Because inactive companies cannot be selected as active context, their activity is not viewable through the company activity endpoint in this version.

Migration `0005_audit_logs` creates the audit schema after `0004_administrators` and is applied to the local PostgreSQL database. The real table, constraints, indexes and `ON DELETE RESTRICT` foreign keys were inspected successfully.

No historical audit backfill was performed. The only audit row is the explicitly approved authenticated runtime verification event for `CompanyTest`.

The verification called `POST /api/v1/companies/0138bfbe-80af-4304-ad91-14d1914a9869/activate` and then read `GET /api/v1/companies/0138bfbe-80af-4304-ad91-14d1914a9869/activity`; both returned HTTP 200. `CompanyTest` remained active, so the stored `company.activated` event records company scope, administrator actor, `changed: false`, and `active` as both the previous and new status. Its company and resource IDs match `CompanyTest`, and its actor ID matches the authenticated local administrator. No actual company state was changed.
EOF

printf '%s\n' "Project administration documents updated."

if [[ -x "${PROJECT_ROOT}/scripts/maintenance/update-inventory.sh" ]]; then
    printf '%s\n' "Updating project inventory..."
    "${PROJECT_ROOT}/scripts/maintenance/update-inventory.sh"
else
    printf '%s\n' "WARNING: update-inventory.sh is missing or not executable."
fi

printf '\n%s\n' "Project status update completed successfully."
