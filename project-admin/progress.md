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
