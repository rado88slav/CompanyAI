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

The Company domain, Company Settings, administrator authentication, Active Company Context, Audit Logging, Company Memberships and Roles, and Approval Manager foundations are operational locally. Company Memberships and Roles was committed as `d311521 Add company memberships and roles`. Approval Manager and Authorization Policies was committed as `da9386c Add approval manager and authorization policies` and pushed successfully to `origin/main`; local `main`, `origin/main` and `origin/HEAD` were verified at `da9386c` immediately after the push.

The working tree was clean immediately after that push. This subsequent project-status synchronization is a new documentation-only working-tree change pending its own review and commit.

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
- Company Memberships and Roles committed as `d311521 Add company memberships and roles`;
- Approval Manager and Authorization Policies committed as `da9386c Add approval manager and authorization policies`;
- commit `da9386c` pushed successfully to `origin/main`;
- local `main`, `origin/main` and `origin/HEAD` verified at `da9386c`, with a clean working tree immediately after the push;
- this later documentation synchronization remains a separate uncommitted change pending review;
- first-class company-owned Agent Identity foundation with persistent agents, credentials and exact permissions;
- administrator identity and agent identity remain cryptographically and semantically separate;
- versioned one-time machine credentials use HMAC-SHA256 with a dedicated server-side pepper;
- short-lived agent JWTs use dedicated issuer, audience, signing configuration and database revalidation on every request;
- agent, credential, company and `auth_version` changes invalidate authentication immediately;
- agent lifecycle, credential rotation/revocation and permission history are append-only or soft-state transitions with atomic audit events;
- administrator agent-management APIs and internal credential exchange/identity endpoints;
- Approval Manager agent actor foreign keys and trusted authenticated-identity action helper;
- schema-only migration `0008_agent_identity` created after `0007_approval_manager` and applied locally;
- immediately after Agent Identity verification, real PostgreSQL was at `0008_agent_identity`; the three agent tables existed and contained zero rows;
- backend Compose propagates all six Agent Authentication settings by placeholder; rebuilt runtime verification confirms invalid agent JWT responses return HTTP 401;
- Agent Identity and Internal Agent Authentication committed as `201268b Add agent identity and internal authentication`;
- secure Tool Registry metadata, company availability and historical agent grants are implemented without execution behavior;
- migration `0009_tool_registry` follows `0008_agent_identity` and is applied locally; immediately after Tool Registry verification, real PostgreSQL was at `0009_tool_registry` and all three Tool Registry tables contained zero rows;
- rebuilt backend is healthy, readiness confirms database reachability, OpenAPI exposes 55 paths including all 14 Tool Registry paths, and invalid agent JWT access to `/api/v1/internal/tools` returns HTTP 401;
- trusted runtime descriptors are registered only by Python code; database rows never contain import paths, commands or executable payloads;
- randomized communication scheduling deferred to the Campaign Scheduler;

Remaining:

- repeatable development seed automation.

---

## Automated Verification

Latest backend verification:

    292 passed, 1 warning

The warning is a non-blocking Starlette `TestClient` deprecation warning.

Alembic migration chain:

    <base> -> 0001_initial -> 0002_companies -> 0003_company_settings -> 0004_administrators -> 0005_audit_logs -> 0006_company_memberships -> 0007_approval_manager -> 0008_agent_identity -> 0009_tool_registry -> 0010_provider_connections -> 0011_provider_execution (head, applied to the real development database)

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
    POST  /api/v1/companies/{company_id}/agents
    GET   /api/v1/companies/{company_id}/agents
    GET   /api/v1/companies/{company_id}/agents/{agent_id}
    PATCH /api/v1/companies/{company_id}/agents/{agent_id}
    POST  /api/v1/companies/{company_id}/agents/{agent_id}/activate
    POST  /api/v1/companies/{company_id}/agents/{agent_id}/deactivate
    POST  /api/v1/companies/{company_id}/agents/{agent_id}/revoke
    GET   /api/v1/companies/{company_id}/agents/{agent_id}/credentials
    POST  /api/v1/companies/{company_id}/agents/{agent_id}/credentials
    POST  /api/v1/companies/{company_id}/agents/{agent_id}/credentials/{credential_id}/rotate
    POST  /api/v1/companies/{company_id}/agents/{agent_id}/credentials/{credential_id}/revoke
    GET   /api/v1/companies/{company_id}/agents/{agent_id}/permissions
    POST  /api/v1/companies/{company_id}/agents/{agent_id}/permissions
    POST  /api/v1/companies/{company_id}/agents/{agent_id}/permissions/{permission_id}/revoke
    POST  /api/v1/internal/agent-auth/token
    GET   /api/v1/internal/agent-auth/me
    POST  /api/v1/tools
    GET   /api/v1/tools
    GET   /api/v1/tools/{tool_id}
    PATCH /api/v1/tools/{tool_id}
    POST  /api/v1/tools/{tool_id}/activate
    POST  /api/v1/tools/{tool_id}/deactivate
    POST  /api/v1/tools/{tool_id}/deprecate
    GET   /api/v1/companies/{company_id}/tools
    GET   /api/v1/companies/{company_id}/tools/{tool_id}
    POST  /api/v1/companies/{company_id}/tools/{tool_id}/enable
    POST  /api/v1/companies/{company_id}/tools/{tool_id}/disable
    GET   /api/v1/companies/{company_id}/agents/{agent_id}/tools
    POST  /api/v1/companies/{company_id}/agents/{agent_id}/tools/{tool_id}/grant
    POST  /api/v1/companies/{company_id}/agents/{agent_id}/tool-grants/{grant_id}/revoke
    GET   /api/v1/internal/tools
    GET   /api/v1/internal/tools/{tool_key}
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
- Approval Manager: implemented, automatically verified and committed as `da9386c Add approval manager and authorization policies`
- Approval migration `0007_approval_manager`: applied locally; request, decision and usage tables empty; policy table contains 6 active and 6 revoked records
- Authorization safety bootstrap: first approved run used the old image and created six legacy-scoped platform policies
- Authorization safety repair: explicitly approved and completed atomically for all six legacy policies
- Real authorization data: 12 policies total, 6 active `any`/null and 6 preserved revoked legacy policies; no requests, decisions or usages
- Authorization audit data: 12 create events and 6 revoke events; historical records preserved
- Safety invariant: independently verified with exactly one valid active policy per action and no unexpected or duplicate active bootstrap policies
- Runtime external actions: none executed
- Agent Identity: committed as `201268b Add agent identity and internal authentication`
- Agent migration `0008_agent_identity`: applied locally; the database was at this revision when Agent Identity was verified
- Real agent data: `agents`, `agent_credentials` and `agent_permissions` each contain zero rows
- Internal agent authentication: Compose propagation and rebuilt runtime verification are complete; invalid raw credentials and invalid agent JWTs return HTTP 401
- Tool Registry: implemented and automatically verified, uncommitted
- Provider Connections: implemented and runtime-verified; eight trusted descriptors, metadata-only APIs and AES-256-GCM credential storage foundation are present
- Provider Connections migration `0010_provider_connections`: applied locally; the database was at this revision when both empty provider tables were verified
- Provider Connections runtime: healthy backend, database readiness reachable, 65 OpenAPI paths with 10 Provider Connections paths, authenticated company-scoped listing returns HTTP 200, and no external calls or plaintext retrieval API exist
- Provider Connections validation: complete backend suite, focused tests, compilation, security scan and deterministic generator verification passed; generated_matches_current=yes and whitespace validation passed
- Provider Execution: dry-run-only foundation implemented with Approval Manager evaluator decisions, atomic authorization usage reservation/consumption, administrator and agent approval-backed execution, exact Tool Registry grants for agents, and complete lifecycle audit actions
- Provider Execution migration and schema: `0011_provider_execution` is applied to the real development database at head; PostgreSQL constraints and indexes are verified, and `provider_executions` and `provider_execution_attempts` each contain zero rows
- Provider Execution runtime: rebuilt backend is healthy and database-ready; authenticated registry returns exactly 22 operations across 8 providers, company-scoped listing returns an empty `50/0` page, and OpenAPI exposes 74 total paths including 9 Provider Execution paths
- Provider Execution safety: no real connection, credential, approval, execution or attempt was created; no external provider operation ran; live mode remains fail-closed
- Development credential key: `CREDENTIAL_ENCRYPTION_KEY` was safely rotated while `provider_credentials` contained zero rows; the force-recreated backend uses the rotated key and passed health and database-readiness checks
- Development secret rotation: after a local terminal exposure, all affected application secrets and `POSTGRES_PASSWORD` were rotated without displaying replacements; `agent_credentials` and `provider_credentials` were empty beforehand, and backend health plus database readiness were verified afterward without application-row changes
- Credential key startup validation: application creation fails fast before FastAPI startup for missing, empty, malformed or wrong-length configuration; accepted values are exactly 64 hexadecimal ASCII characters or 44-character padded Base64/Base64url decoding to exactly 32 bytes
- Tool Registry migration `0009_tool_registry`: applied locally; the database was at this revision when Tool Registry was verified
- Tool Registry schema: all three tables exist; `tool_definitions = 0`, `company_tools = 0`, `agent_tool_grants = 0`
- Tool Registry runtime: backend healthy, readiness database reachable, OpenAPI 55 paths with all 14 Tool Registry paths, invalid internal agent JWT returns HTTP 401
- Provider Connections code is implemented and runtime-verified with eight trusted in-process descriptors, company-scoped connection metadata and encrypted credential history. Provider Execution is available only as the separately authorized dry-run foundation; no live provider execution exists.
- Migration `0010_provider_connections` is applied locally; both provider tables exist and contain zero rows. No live external provider integrations are configured and no provider APIs are called.
- Credential payloads use the pinned `cryptography` AES-256-GCM boundary with identity-bound associated data. The development key is securely configured locally; its value is not stored in Git or documented.
- The backend image was rebuilt successfully and the healthy runtime was verified with 65 OpenAPI paths and 10 Provider Connections paths.
- The safe development rotation is complete. No real credentials or provider executions were created, and no external provider operation ran.
- Production secret management and key provisioning remain future work.
- Startup configuration failures use one deterministic sanitized error and never include key, hash, ciphertext, nonce or payload material.
- A key ID/keyring and re-encryption workflow are still required for future rotation when credentials exist.
- `scripts/setup/create-env.sh --force` must not be used for key-only rotation because it replaces the entire `.env` file.
- No provider API calls, OAuth flows, connectivity tests, plaintext retrieval APIs or tool execution are implemented.
- Tool execution and provider calls: intentionally not implemented
- Bearer-protected administration routes: operational
- Company persistence: verified
- Company Settings persistence: verified
- Automated tests: passing
- Company Memberships Git commit: `d311521 Add company memberships and roles`
- Approval Manager Git commit: `da9386c Add approval manager and authorization policies`
- Remote synchronization: `da9386c` pushed to `origin/main`; local `main`, `origin/main` and `origin/HEAD` verified at that commit
- Post-push state: working tree was clean; the current documentation synchronization is a new uncommitted change

---

## Next Work

Continue Phase 3 with:

1. review the uncommitted but runtime-verified Provider Connections and Provider Execution foundations;
2. design production secret provisioning and a key ID/keyring plus re-encryption workflow before production use or any future rotation with stored credentials;
3. continue with Tool Execution and Agent Runtime only as a separately approved task;
4. commit and push only after explicit approval.

---

## Last Updated

2026-07-24
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
- [x] Resolve active member access at request time with a platform superuser override.
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

### 7. Company Memberships and Roles

- [x] Define owner, admin, operator and viewer roles.
- [x] Add database-backed request-time company authorization.
- [x] Protect the last active owner with Company row locking.
- [x] Add membership and current-administrator membership APIs.
- [x] Restrict platform Company CRUD to superusers.
- [x] Add membership audit actions and atomic transactions.
- [x] Create schema-only migration `0006_company_memberships`.
- [x] Apply migration `0006_company_memberships` after approval.
- [x] Verify the module against PostgreSQL.
- [x] Execute the explicit owner bootstrap after approval.

### 8. Development Seed Data

### 8. Approval Manager and Authorization Policies

- [x] Define approval requests and append-only decisions.
- [x] Define allow, require-approval and block policies.
- [x] Define the reservation usage ledger.
- [x] Add human administrator APIs and company role permissions.
- [x] Add internal evaluator and atomic reservation services without HTTP exposure.
- [x] Create schema-only migration `0007_approval_manager`.
- [x] Apply migration `0007_approval_manager` after approval.
- [x] Execute the controlled authorization safety legacy-scope repair after separate approval.
- [x] Verify policy counts, audit counts and strict post-repair invariants independently.
- [x] Verify the empty Approval Manager schema and read-only collections against local PostgreSQL.

### 9. Development Seed Data

### 9. Agent Identity and Internal Agent Authentication

- [x] Define company-owned agents and lifecycle states.
- [x] Add one-time HMAC-protected machine credentials.
- [x] Add short-lived, separately configured agent JWTs.
- [x] Revalidate agent, credential, company and auth version per request.
- [x] Add exact revocable permission history.
- [x] Add administrator management and internal authentication endpoints.
- [x] Integrate agent identities with Approval Manager foreign keys.
- [x] Add atomic agent audit events and security tests.
- [x] Create schema-only migration `0008_agent_identity`.
- [x] Apply migration `0008_agent_identity` after explicit approval.
- [x] Verify the empty Agent Identity schema against real PostgreSQL without exposing secrets.
- [ ] Recreate the backend container and re-verify invalid agent JWT handling after explicit approval.

### 10. Tool Registry

- [x] Add a global non-executable tool catalog.
- [x] Add company tool enablement and immediate disable semantics.
- [x] Add authoritative historical agent tool grants.
- [x] Add exact tool-key and recursive schema safety validation.
- [x] Add trusted in-process runtime descriptor registry.
- [x] Add administrator and authenticated-agent APIs without execution endpoints.
- [x] Derive exact Approval Manager actions from authenticated agents and persisted tools.
- [x] Audit every successful Tool Registry mutation.
- [x] Create schema-only migration `0009_tool_registry`.
- [x] Apply migration `0009_tool_registry` after explicit approval.
- [x] Verify the empty Tool Registry schema against real PostgreSQL.
- [x] Verify rebuilt backend health, readiness, all 14 Tool Registry paths and invalid-agent-JWT HTTP 401 behavior.

### 11. Provider Connections

- [x] Add eight immutable trusted provider descriptors in application code.
- [x] Add company-isolated connection metadata and encrypted credential history models.
- [x] Add metadata-only catalog, connection and credential lifecycle APIs.
- [x] Add atomic audit logging and owner/admin mutation versus operator/viewer read RBAC.
- [x] Create schema-only migration `0010_provider_connections`.
- [x] Rebuild the backend image with the pinned `cryptography` dependency and run the complete suite after explicit approval.
- [x] Apply migration `0010_provider_connections` after explicit approval.
- [x] Verify the empty schema against PostgreSQL.
- [x] Safely rotate the development credential encryption key while `provider_credentials` is empty and verify the force-recreated backend health and readiness.
- [x] Add fail-fast startup validation for a missing, empty, malformed or wrong-length credential encryption key.
- [ ] Define production secret management and production key provisioning.
- [ ] Add a key ID/keyring and re-encryption workflow for future rotation when credentials exist.
- [x] Document that `scripts/setup/create-env.sh --force` replaces the entire `.env` and must not be used for key-only rotation.
- [x] Implement the dry-run-only Provider Execution foundation with Approval Manager authorization and agent Tool Registry grant enforcement.
- [x] Apply migration `0011_provider_execution` to the real development database after explicit approval.
- [x] Verify the empty Provider Execution schema, authenticated registry and company-scoped listing against the rebuilt backend.
- [ ] Review and commit the Provider Execution foundation after explicit approval.

### 11. Development Seed Data

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
- [x] Company access roles and membership isolation are implemented.
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

Active ordinary administrators select only active companies for which they have an active database membership. Active platform superusers may select any active company without membership.

Authentication alone does not grant access to every company. Company-owned endpoints must resolve and authorize the selected context before accessing company data.

When a company-owned route also contains `company_id` in its URL, the URL UUID and `X-Company-ID` UUID must match. A mismatch must be rejected before the service performs a read or write.

Service and repository layers must continue to receive `company_id` explicitly and filter company-owned queries by it. Active Company Context must not use process-global or other mutable shared state.

## 020 — Audit Logging

Audit logs use an append-only application contract. Audit repositories and APIs do not expose update or delete operations, and audit records do not contain an `updated_at` field.

Company mutations and their audit records use the same request-scoped SQLAlchemy session and are committed exactly once by the Company service. A mutation or audit failure rolls back the complete transaction.

Actions use normalized lowercase dotted names. Company actions are `company.created`, `company.updated`, `company.activated` and `company.deactivated`; membership actions are `company_membership.created`, `company_membership.role_changed`, `company_membership.activated` and `company_membership.deactivated`.

Audit details contain only explicit non-secret allowlisted JSON objects. Passwords, hashes, tokens, keys, credentials, request headers, unrestricted request payloads and secret setting values must never be stored.

Company activity is isolated through Active Company Context. Because inactive companies cannot be selected as active context, their activity is not viewable through the company activity endpoint in this version.

Migration `0005_audit_logs` creates the audit schema after `0004_administrators` and is applied to the local PostgreSQL database. The real table, constraints, indexes and `ON DELETE RESTRICT` foreign keys were inspected successfully.

No historical audit backfill was performed. The only audit row is the explicitly approved authenticated runtime verification event for `CompanyTest`.

The verification called `POST /api/v1/companies/0138bfbe-80af-4304-ad91-14d1914a9869/activate` and then read `GET /api/v1/companies/0138bfbe-80af-4304-ad91-14d1914a9869/activity`; both returned HTTP 200. `CompanyTest` remained active, so the stored `company.activated` event records company scope, administrator actor, `changed: false`, and `active` as both the previous and new status. Its company and resource IDs match `CompanyTest`, and its actor ID matches the authenticated local administrator. No actual company state was changed.

## 021 — Company Memberships and Roles

Company authorization is database-backed and evaluated on every request. Roles are `owner`, `admin`, `operator` and `viewer`; platform superusers retain an explicit platform override and alone may use Company CRUD.

Owners manage all roles. Admins manage only operator and viewer memberships and cannot modify themselves. Operators and viewers have read-only Settings and Activity access. Membership list and management are limited to owners and admins according to the target-role rules.

The last active owner cannot be demoted or deactivated, including by a platform superuser. Owner-affecting mutations lock the parent Company row with `SELECT ... FOR UPDATE` before counting active owners.

Active Company Context remains stateless and header-based. Ordinary administrators need an active membership; inactive or absent memberships produce a generic forbidden response on the next request without JWT refresh. Repository queries retain explicit `company_id` filtering.

Future company creation atomically inserts the Company, an active owner membership for the creating superuser, and both audit events before one commit. Membership mutations and audit events likewise share one request-scoped transaction.

Migration `0006_company_memberships` is schema-only and follows `0005_audit_logs`. It is applied locally, and the membership table, constraints, indexes and foreign keys are verified against PostgreSQL. No historical membership backfill was performed.

The explicit idempotent bootstrap completed successfully for CompanyTest. The authenticated platform superuser has one active owner membership, and the corresponding `company_membership.created` audit persistence is verified. The Company Memberships and Roles foundation was committed as `d311521 Add company memberships and roles`.

## 022 — Approval Manager and Authorization Policies

Approval decisions and authorization enforcement are separate concerns. Requests and immutable decisions capture human intent; policies capture allow, require-approval and block rules; the usage ledger is the authoritative reservation and consumption record.

Evaluation is fail-safe and deterministic: platform minimum risk cannot be lowered, block wins, always-require approval accepts only an exact decision-backed single action, and exactly one matching grant is selected without combining limits. Unknown actions are at least high risk.

Usage reservation locks the selected policy with `SELECT ... FOR UPDATE`, rechecks all selectors and limits, inserts the reservation and audit event, and commits once. External side effects remain outside this database transaction and will require provider idempotency keys and reconciliation.

Only authenticated human administrator APIs are registered. Internal runtime evaluation and reservation are Python services only; internal HTTP routes remain disabled until Agent Identity and agent authentication exist. Randomized sending cadence belongs to the future Campaign Scheduler, which may operate only within these maximum authorization boundaries.

Migration `0007_approval_manager` is schema-only, follows `0006_company_memberships`, and is applied locally. The request, decision and usage tables are empty. The authorization policy table contains 12 records: six active wildcard platform safety policies and six preserved revoked legacy policies. No runtime external actions were executed. Approval Manager and Authorization Policies was committed as `da9386c Add approval manager and authorization policies` and pushed successfully to `origin/main`.

The first local application attempt exposed six foreign-key names longer than PostgreSQL's 63-byte identifier limit. PostgreSQL transactional DDL rolled back the complete attempt, so the database remained at `0006_company_memberships` and none of the four Approval Manager tables or records remained after that failed attempt. The identifiers were shortened before retry.

After the identifier correction, migration `0007` was applied successfully and the current database revision became `0007_approval_manager (head)`. All four tables exist, were empty immediately after migration verification, and all 14 foreign keys use `ON DELETE RESTRICT`. The later bootstrap and repair operations created only the 12 authorization policy rows described below; requests, decisions and usages remain empty.

The first read-only runtime check returned HTTP 200 for approval requests and HTTP 500 for authorization policies because pagination arguments were incorrectly forwarded to `count_policies`; authorization usages had the same latent defect. Pagination filters and page controls were then separated consistently. Final authenticated read-only verification returned HTTP 200 for approval requests, authorization policies and authorization usages. Each response contained `items: []`, `total: 0`, `limit: 1` and `offset: 0`. No approval requests, decisions, policies or usages were created during verification.

Safety policy review found that exact `scope_type = company` matching would leave campaign, batch, resource and future concrete scopes uncovered. The reserved policy scope `any` now matches independently of an action's concrete resource scope and requires a null `scope_id`. Exact scope types and IDs remain narrower and rank above wildcard policies. Platform rules remain platform-wide, company rules remain isolated by `company_id`, and block and always-require-approval precedence is unchanged.

The wildcard code was complete, but the backend container had not yet been rebuilt when the first approved platform bootstrap ran. The old image created six active platform policies with `scope_type = company` and null `scope_id`, plus six matching `authorization_policy.created` audit events. Read-only verification detected the mismatch immediately. Approval requests, decisions and usages remained empty, and no external action was executed. The backend was then rebuilt with the correct `any`/null code.

Bootstrap idempotence now requires an exact match across the complete security-relevant policy definition. Every mismatch is refused by default. The explicit `--repair-legacy-scope` path may revoke and replace only the exact historical bootstrap shape, writes revoke and create audit events, and commits all six changes atomically. After implementation and isolated testing, the user explicitly approved the real platform repair. It completed successfully in one transaction: six legacy policies were revoked and preserved, six new active `any`/null policies were created, and six revoke plus six additional create audit events were appended.

Independent read-only verification confirmed 12 policies total, split into six active and six revoked, with zero approval requests, decisions and usages. Audit totals are 12 `authorization_policy.created` events and six `authorization_policy.revoked` events. Each active policy has exactly one create event; each revoked legacy policy retains its historical create event and has exactly one revoke event. The strict invariant check found exactly one valid active policy for every safety action, exactly six expected revoked legacy policies, no unexpected or duplicate active bootstrap policies, and all expected audit records. No policy was deleted, historical records were preserved, and no external action was executed. Normal bootstrap is expected to be idempotent after repair, but no additional real bootstrap run has been performed.

After commit `da9386c` was pushed, local `main`, `origin/main` and `origin/HEAD` were all verified at `da9386c`, and the working tree was clean. This later documentation synchronization is not part of that commit and remains a new working-tree change pending its own review and commit.

## 023 — Agent Identity and Internal Agent Authentication

Agents are first-class company-owned machine identities and never administrator identities. Administrator access tokens use the existing human authentication contract; agent JWTs use dedicated signing configuration, issuer, audience, `token_type = agent`, credential ID and agent `auth_version`. Each authenticated agent request revalidates the agent, credential and company from PostgreSQL so lifecycle changes, credential rotation and revocation take effect immediately.

Machine credentials use the versioned `cai_agent_v1_<public_id>.<secret>` shape. The public ID supports direct lookup; the secret has at least 256 bits of entropy and is stored only as HMAC-SHA256 using `AGENT_CREDENTIAL_PEPPER`. Plaintext is returned exactly once after creation or rotation and is excluded from list schemas, audit details and logs. The pepper and dedicated JWT secret are environment-only values; `.env.example` contains placeholders and the real `.env` is not modified by this module.

Permissions are exact normalized keys with preserved revoked history and no wildcard semantics. Agents, credentials and permissions are isolated by explicit `company_id`; credentials and permissions use composite company/agent foreign keys, and credential rotation lineage is database-constrained to the same company and agent. Agent revocation permanently revokes the identity, active credentials and active permissions in one transaction. Security-sensitive mutations and their audit events commit atomically.

Migration `0008_agent_identity` creates `agents`, `agent_credentials` and `agent_permissions`, extends audit actors with agent identity, and adds the three deferred Approval Manager agent foreign keys. It is a static schema-only migration after `0007_approval_manager` and is applied locally. Backend Compose propagates the six Agent Authentication variables through tracked placeholders without storing their values; rebuilt runtime verification confirms invalid raw credentials and invalid agent JWTs return HTTP 401. No real agents, credentials or permissions exist. Retell agents remain future external voice executors; Agent Runtime and external provider integrations are not implemented here. The foundation is committed as `201268b Add agent identity and internal authentication`.

## 024 — Tool Registry

Tool definitions are global metadata and authorization configuration, never executable payloads. Database fields reject secret-bearing and executable/import/shell keys recursively. Exact normalized tool keys are immutable identifiers, high and critical risks require approval, and no hard-delete or execution endpoint exists.

Company availability and agent grants are separate company-scoped records. `agent_tool_grants` is the sole authoritative source for agent-to-tool access and does not mutate `agent_permissions`. Composite foreign keys bind every grant to both its company-owned agent and the same company's tool availability record. Effective access requires active tool metadata, enabled company availability, an active historical grant and a currently authenticated active agent. Disabling or revoking any layer takes effect on the next query.

Runtime descriptors exist only in a trusted in-process registry populated directly by application code. Exact lookup and duplicate rejection are deterministic; no dynamic import, `eval`, `exec`, provider call or shell execution exists. Future Approval Manager input derives `tool.execute.<tool-key>` from persisted metadata and the authenticated agent identity, never caller-supplied actor or action values.

Migration `0009_tool_registry` statically creates `tool_definitions`, `company_tools` and `agent_tool_grants` after `0008_agent_identity` and is applied locally. At the Tool Registry verification point, the real database was at `0009_tool_registry`; all three tables existed and each contained zero rows. The rebuilt backend was healthy, readiness confirmed database reachability, OpenAPI contained 55 paths including all 14 Tool Registry paths, and an invalid agent JWT against `/api/v1/internal/tools` returned HTTP 401. Tool execution remains a future Agent Runtime responsibility.

## 025 — Provider Connections and encrypted credentials

Provider types are immutable trusted Python descriptors, not database-defined implementations. Exact normalized keys select only descriptor metadata; the database stores no import paths, modules, source, commands or callable references. Provider Execution is implemented as a dry-run-only, Approval Manager-authorized foundation; live external adapter calls remain future work.

`provider_connections` holds company-scoped safe metadata. `provider_credentials` holds append-only encrypted credential versions with company-safe composite foreign keys, one-active-version enforcement and same-connection rotation lineage. No API exposes ciphertext, nonce or plaintext. Connection and credential mutations are audited and committed atomically.

Credential bundles use AES-256-GCM from the pinned `cryptography` dependency. Canonical JSON is authenticated with associated data binding company, connection, credential, provider key and encryption version. Configuration accepts only descriptor-allowed fields and recursively rejects secret-bearing and executable fields. Decryption is available only through a narrow trusted in-process resolver.

Migration `0010_provider_connections` follows `0009_tool_registry` and is applied locally. Before development key rotation, a read-only count confirmed that `provider_credentials` contained zero rows, so rotation could not orphan encrypted data. `CREDENTIAL_ENCRYPTION_KEY` was then replaced atomically only in the local `.env` with a cryptographically random 32-byte padded Base64url value; the remaining `.env` entries were preserved and its permissions remained `600`. The key value and its hash were not displayed and must never be documented or stored in Git.

The backend container was force-recreated without an image rebuild and was verified to use the current local key, which decodes to exactly 32 bytes. `GET /api/v1/health` returns HTTP 200 with `status=ok`, and `GET /api/v1/health/ready` returns HTTP 200 with `database=reachable`. No database rows were modified, no real provider credentials were created, and no real provider execution or external provider call occurred.

After a subsequent local terminal exposure, `APP_SECRET_KEY`, `AGENT_JWT_SECRET`, `AGENT_CREDENTIAL_PEPPER`, `CREDENTIAL_ENCRYPTION_KEY` and `POSTGRES_PASSWORD` were rotated without displaying replacement values or hashes. Read-only checks before rotation confirmed that both `agent_credentials` and `provider_credentials` contained zero rows. The four application secrets were replaced atomically only in the local `.env`, whose permissions remained `600`, while the PostgreSQL role and local password were updated consistently. The backend was force-recreated without an image rebuild; health and database readiness returned HTTP 200 afterward. No application table rows were modified, and no credential, approval or execution was created. The local `.env` remains outside Git, and no secret value belongs in documentation.

Application creation now calls the same trusted key decoder used by credential encryption before constructing FastAPI. Startup fails for a missing, empty, malformed or wrong-length key, so health and readiness cannot succeed with invalid configuration. Accepted values are exactly 64 hexadecimal ASCII characters or exactly 44-character padded Base64/Base64url that decodes to exactly 32 bytes. Failures use one deterministic sanitized message and never include the key, its hash, ciphertext, nonce or secret payload material.

Production secret management and production key provisioning remain future work. Future rotation after credentials exist requires a key ID/keyring and a controlled re-encryption workflow. `scripts/setup/create-env.sh --force` is not a key-rotation mechanism because it replaces the entire `.env` file.

## 026 — Provider Execution and Approval Manager integration

Provider Execution uses the existing Authorization Evaluator and Authorization Usage ledger rather than a second approval mechanism. Approval-required executions remain `pending_authorization` without a matching active allow policy. The evaluator validates company, administrator or agent subject, exact provider operation tool identifier, risk, company scope and provider connection; a successful decision is reserved against the execution ID before any attempt starts. Single-use policy consumption, usage finalization, execution state, attempt history and audit events are committed together.

Agent execution requires both an exact active Tool Registry grant and an independently valid Approval Manager authorization. Administrator and agent identities are derived from authenticated request context. Authorization policy lineage is stored through a restrictive foreign key, authorization usage is linked to the same-company execution, and audit events preserve the real administrator or agent actor without payloads or secrets.

Migration `0011_provider_execution` follows `0010_provider_connections` and is applied to the real development database at head. PostgreSQL verification confirmed the two execution tables, their restrictive foreign keys, checks, uniqueness constraints and indexes; both tables contain zero rows. The rebuilt backend is healthy and database-ready. Authenticated runtime checks return exactly 22 operations across 8 providers and an empty company-scoped execution page; OpenAPI contains 74 paths, including 9 Provider Execution paths. The implementation remains dry-run-only, live adapters fail closed, and no real provider credential, approval, execution, attempt or external provider call was created during verification.
EOF

printf '%s\n' "Project administration documents updated."

if [[ -x "${PROJECT_ROOT}/scripts/maintenance/update-inventory.sh" ]]; then
    printf '%s\n' "Updating project inventory..."
    "${PROJECT_ROOT}/scripts/maintenance/update-inventory.sh"
else
    printf '%s\n' "WARNING: update-inventory.sh is missing or not executable."
fi

printf '\n%s\n' "Project status update completed successfully."
