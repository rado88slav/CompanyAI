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
