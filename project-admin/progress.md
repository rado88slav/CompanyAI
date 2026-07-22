# Project Progress

## Current Phase

**Phase 3 — Company and Administration Core: In Progress**

The Company domain, Company Settings, administrator authentication, Active Company Context, Audit Logging and Company Memberships and Roles foundations are operational locally. The uncommitted Approval Manager foundation is implemented and automatically verified; migration `0007_approval_manager` is applied locally.

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
- database-backed company context selection for active members, with platform superuser override;
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
- `CompanyMembership` model with owner, admin, operator and viewer roles;
- request-time database authorization and centralized company permissions;
- membership management and current-administrator membership APIs;
- last-active-owner protection with parent Company row locking;
- automatic owner membership and audit event for future company creation;
- membership audit actions and atomic mutation transactions;
- explicit idempotent owner bootstrap command, completed successfully for CompanyTest;
- schema-only Alembic migration `0006_company_memberships`, applied locally;
- membership table, constraints, indexes and foreign keys verified against PostgreSQL;
- active owner membership created for the authenticated CompanyTest superuser;
- `company_membership.created` audit persistence verified;
- complete Company Memberships and Roles backend suite verification;
- four-table Approval Manager and Authorization Policies foundation;
- deterministic risk catalog, policy evaluation and atomic usage reservation services;
- authenticated, company-isolated human approval, policy and usage APIs;
- internal agent HTTP routes intentionally disabled until Agent Identity exists;
- schema-only migration `0007_approval_manager` applied locally after its identifier correction;
- first local `0007` application attempt failed on an overlong PostgreSQL identifier and transactional DDL rolled back the complete migration;
- immediately after that failed attempt, local PostgreSQL remained at `0006_company_memberships`, with no Approval Manager tables or records left behind;
- the six overlong foreign-key names were corrected before any migration retry;
- all four Approval Manager tables exist locally; before the first bootstrap run all four contained no records;
- read-only runtime verification returned HTTP 200 for approval requests, then exposed an HTTP 500 policy-list pagination defect because `limit` and `offset` reached `count_policies`;
- authorization usage listing contained the same latent pagination defect;
- service pagination now separates filters from `limit` and `offset` consistently for requests, policies and usages;
- final authenticated read-only runtime verification returned HTTP 200 for approval requests, authorization policies and authorization usages;
- each final collection response contained `items: []`, `total: 0`, `limit: 1` and `offset: 0`;
- all 14 Approval Manager foreign keys are verified with `ON DELETE RESTRICT`;
- reserved authorization policy scope `any` introduced for safety rules across every concrete resource scope;
- platform and company bootstrap definitions now use `scope_type: any` with a null `scope_id`;
- wildcard scope changes only resource matching: company isolation remains enforced by `company_id`;
- wildcard code was completed before the backend container was rebuilt;
- the first approved platform bootstrap therefore ran the old container code and created six active platform policies with legacy `company`/null scope plus six matching historical create audit events;
- read-only verification detected the scope mismatch immediately; no approval requests, decisions or usages were created and no external action was executed;
- the rebuilt backend now contains the correct `any`/null definitions;
- ordinary bootstrap verification compares the complete security-relevant definition and refuses every mismatch;
- controlled `--repair-legacy-scope` support is implemented and tested for only the exact legacy bootstrap shape;
- the user explicitly approved the controlled platform repair, which completed all six replacements in one transaction;
- all six legacy `company`/null policies are preserved as revoked, and six new active `any`/null platform policies exist;
- authorization policy totals are 12 records: 6 active and 6 revoked; approval requests, decisions and usages remain empty;
- audit totals are 12 `authorization_policy.created` events and 6 `authorization_policy.revoked` events, with historical events preserved;
- an independent strict invariant check confirmed exactly one valid active safety policy per action, exactly six expected revoked legacy policies, no unexpected or duplicate active bootstrap policies, and all expected audit events;
- no policy was deleted and no external action was executed;
- normal bootstrap is expected to be idempotent after repair, but it has not been executed again against the real database;
- randomized communication scheduling deferred to the Campaign Scheduler;

Remaining:

- repeatable development seed automation.

---

## Automated Verification

Latest backend verification:

    172 passed, 1 warning

The warning is a non-blocking Starlette `TestClient` deprecation warning.

Alembic migration chain:

    <base> -> 0001_initial -> 0002_companies -> 0003_company_settings -> 0004_administrators -> 0005_audit_logs -> 0006_company_memberships -> 0007_approval_manager (head, applied locally)

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
    POST  /api/v1/companies/{company_id}/memberships
    GET   /api/v1/companies/{company_id}/memberships
    GET   /api/v1/companies/{company_id}/memberships/{membership_id}
    PATCH /api/v1/companies/{company_id}/memberships/{membership_id}/role
    POST  /api/v1/companies/{company_id}/memberships/{membership_id}/activate
    POST  /api/v1/companies/{company_id}/memberships/{membership_id}/deactivate
    GET   /api/v1/company-memberships/me
    POST  /api/v1/companies/{company_id}/approval-requests
    GET   /api/v1/companies/{company_id}/approval-requests
    GET   /api/v1/companies/{company_id}/approval-requests/{request_id}
    POST  /api/v1/companies/{company_id}/approval-requests/{request_id}/approve
    POST  /api/v1/companies/{company_id}/approval-requests/{request_id}/deny
    POST  /api/v1/companies/{company_id}/approval-requests/{request_id}/cancel
    GET   /api/v1/companies/{company_id}/authorization-policies
    POST  /api/v1/companies/{company_id}/authorization-policies
    GET   /api/v1/companies/{company_id}/authorization-policies/{policy_id}
    POST  /api/v1/companies/{company_id}/authorization-policies/{policy_id}/revoke
    GET   /api/v1/companies/{company_id}/authorization-usages
    GET   /api/v1/companies/{company_id}/authorization-usages/{usage_id}
    PUT    /api/v1/companies/{company_id}/settings/{category}/{key}
    GET    /api/v1/companies/{company_id}/settings
    GET    /api/v1/companies/{company_id}/settings/{category}/{key}
    DELETE /api/v1/companies/{company_id}/settings/{category}/{key}

Platform Company management routes require an active platform superuser.

The Company Context endpoint and company-scoped routes require `X-Company-ID`. Active members may select their companies according to their role; active platform superusers may select any active company without membership. URL company IDs must match the header context.

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
- Company Memberships and Roles: operational locally
- Membership migration `0006_company_memberships`: applied locally
- Membership schema persistence: verified against PostgreSQL
- CompanyTest membership: one active owner membership for the authenticated superuser
- Membership bootstrap: completed successfully
- Membership audit persistence: `company_membership.created` verified
- Approval Manager: implemented and automatically verified, uncommitted
- Approval migration `0007_approval_manager`: applied locally; request, decision and usage tables empty; policy table contains 6 active and 6 revoked records
- Authorization safety bootstrap: first approved run used the old image and created six legacy-scoped platform policies
- Authorization safety repair: explicitly approved and completed atomically for all six legacy policies
- Real authorization data: 12 policies total, 6 active `any`/null and 6 preserved revoked legacy policies; no requests, decisions or usages
- Authorization audit data: 12 create events and 6 revoke events; historical records preserved
- Safety invariant: independently verified with exactly one valid active policy per action and no unexpected or duplicate active bootstrap policies
- Runtime external actions: none executed
- Bearer-protected administration routes: operational
- Company persistence: verified
- Company Settings persistence: verified
- Automated tests: passing
- Git repository: operational

---

## Next Work

Continue Phase 3 with:

1. review the complete uncommitted Approval Manager work;
2. review the corrected read-only pagination behavior;
3. review the independently verified safety-policy repair state;
4. create the Git commit after explicit approval.

---

## Last Updated

2026-07-22
