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

Application creation validates the active key ID and complete immutable keyring before constructing FastAPI, so health and readiness cannot succeed with missing, empty, malformed, duplicate or ambiguous configuration. Every encoded key is processed by the same trusted decoder used by credential encryption and must be exactly 64 hexadecimal ASCII characters or exactly 44-character padded Base64/Base64url decoding to exactly 32 bytes. Standalone or mixed legacy configuration is rejected. Failures use one deterministic sanitized message and never include keyring JSON, key material, hashes, ciphertext, nonce or secret payload material.

Production secret management and production key provisioning remain future work. Future rotation after credentials exist requires a key ID/keyring and a controlled re-encryption workflow. `scripts/setup/create-env.sh --force` is not a key-rotation mechanism because it replaces the entire `.env` file.

The immutable keyring core exists. Expand migration `0012_credential_keyring_expand` was applied and verified before the contract migration superseded it as head. Its transitional nullable `VARCHAR(64)` `encryption_key_id`, non-null `INTEGER` `encryption_revision` with server default `0`, both check constraints and ordered `(encryption_key_id, id)` index were verified while `provider_credentials` remained empty. No credential payload was read, decrypted, modified or backfilled, and no real credential or external provider execution was created.

Provider Credential model, repository and service integration are keyring-aware. The repository runtime contract now requires non-secret `CREDENTIAL_ENCRYPTION_ACTIVE_KEY_ID` plus secret `CREDENTIAL_ENCRYPTION_KEYRING` JSON. Application creation validates the complete immutable keyring once before FastAPI is constructed and shares that exact keyring with Provider Connections through application state. Standalone `CREDENTIAL_ENCRYPTION_KEY`, legacy-only configuration and ambiguous mixed legacy/new configuration are rejected with the existing sanitized error.

New credentials and business rotations use encryption version 2, store the configured active key ID and revision `0`, and bind the key ID into authenticated associated data alongside the existing company, connection, credential and provider identity. Previous configured keys are decryption-only because encryption always selects the active key.

Historical version-1 rows retain their original AAD. NULL key IDs are readable only when the configured keyring contains the explicit `legacy` entry; the active key is never guessed. Stored v1/v2 key IDs are resolved through the keyring, and missing, malformed or unknown IDs fail closed. Reads do not mutate historical rows.

The real local development runtime cutover is complete. The local environment file was atomically converted from standalone `CREDENTIAL_ENCRYPTION_KEY` to `CREDENTIAL_ENCRYPTION_ACTIVE_KEY_ID` plus secret `CREDENTIAL_ENCRYPTION_KEYRING` while preserving the existing cryptographic key, other entries and permissions `600`. The standalone variable is no longer active. Secret values and hashes were not displayed.

The backend image was rebuilt and the backend container was force-recreated without database changes. Runtime verification confirmed active ID `legacy`, one configured key, a validated immutable keyring, matching configured/runtime active IDs, HTTP 200 health with `status=ok`, and HTTP 200 readiness with reachable database connectivity. No database row, credential, approval or execution was created or modified.

Migration `0013_credential_keyring_contract` is the repository and real development database head. Its fail-closed NULL-reference precondition passed because `provider_credentials` contained zero rows, after which `provider_credentials.encryption_key_id` was verified as `VARCHAR(64) NOT NULL`. No key ID was guessed or backfilled, no payload was decrypted or re-encrypted, and no credential, approval or execution was created.

The backend image rebuild and container recreation with migration 0013 are complete, and the runtime keyring cutover remains healthy and active. Mandatory credential-keyring backend work blocking initial dashboard development is complete, and Dashboard Stage 1 is now implemented as a read-only foundation. Controlled re-encryption tooling remains future work for environments with historical credentials. Production secret-manager/keyring provisioning, old-key retirement and key escrow policy, and backup-retention procedures remain open.

## 026 — Provider Execution and Approval Manager integration

Provider Execution uses the existing Authorization Evaluator and Authorization Usage ledger rather than a second approval mechanism. Approval-required executions remain `pending_authorization` without a matching active allow policy. The evaluator validates company, administrator or agent subject, exact provider operation tool identifier, risk, company scope and provider connection; a successful decision is reserved against the execution ID before any attempt starts. Single-use policy consumption, usage finalization, execution state, attempt history and audit events are committed together.

Agent execution requires both an exact active Tool Registry grant and an independently valid Approval Manager authorization. Administrator and agent identities are derived from authenticated request context. Authorization policy lineage is stored through a restrictive foreign key, authorization usage is linked to the same-company execution, and audit events preserve the real administrator or agent actor without payloads or secrets.

Migration `0011_provider_execution` follows `0010_provider_connections` and is an applied predecessor of current database head `0014_email_workflow`. PostgreSQL verification confirmed the two execution tables, their restrictive foreign keys, checks, uniqueness constraints and indexes; both tables were empty at Provider Execution foundation verification time. The rebuilt backend was healthy and database-ready. Authenticated runtime checks returned exactly 22 operations across 8 providers and an empty company-scoped execution page; OpenAPI contained 74 paths, including 9 Provider Execution paths. The implementation remains dry-run-only, live adapters fail closed, and no real provider credential, approval, execution, attempt or external provider call was created during Provider Execution foundation verification.

## 027 — Dashboard Stage 1 read-only foundation

The first dashboard foundation uses React, TypeScript, Vite and React Router under `frontend/`. Dependencies remain intentionally small: there is no UI framework, state-management framework, charting library, remote font or external image. The desktop-first shell has responsive navigation and accessible focus states. Overview uses manual refresh with explicit loading, error, retry and empty states; all other Stage 1 routes are honest placeholders without fabricated data.

`GET /api/v1/companies/{company_id}/dashboard/summary` is an authenticated read-only endpoint using the existing active-company context and activity, provider, approval and provider-execution read permissions. One aggregate statement returns company-scoped counts, and one bounded deterministic query returns at most five recent audit events. Explicit schemas expose only service status, readiness, environment, application version, seven counts and the safe audit fields `id`, `actor_type`, `action`, `resource_type`, `resource_id` and `created_at`.

The API never serializes ORM objects directly and excludes audit details, credential identifiers and material, encrypted payloads, nonces, key IDs, keyring metadata, hashes and tokens. It performs no writes, credential decryption, provider execution or external call. Stage 1 adds no migration or Docker Compose change. Live email/call integrations, provider mutations, credential forms, approval actions and execution controls remain out of scope. Dashboard Stage 2 should add explicit company-selection and authentication UX plus richer read-only module views before any operational controls.

## 028 — Thin local-test email workflow

The repository implements authenticated test import, normalized inbound
persistence, manual reply proposals, exact SHA-256 approval binding, existing
Approval Manager decisions, explicit deterministic test delivery, provider
execution history and safe audit events. Dashboard routes `/email`,
`/email/:emailId`, `/approvals` and `/audit` use company-scoped APIs.

The Local Test Email Provider needs no credential, makes no network call and
sends no real email. Migration `0014_email_workflow` follows `0013`, is applied
to the real local development database, and was validated through the first
approved local E2E. The historical E2E records are intentionally retained as
local validation evidence; token files were removed during approved cleanup.
