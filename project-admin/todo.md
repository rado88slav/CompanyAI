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
- [x] Integrate the existing keyring into Provider Credential model/repository/service behavior under the transitional one-key `legacy` runtime contract.
- [x] Replace the repository runtime contract with active key ID plus validated keyring JSON and reject standalone legacy configuration.
- [x] Atomically provision the new local development keyring settings after explicit approval while preserving the existing cryptographic key.
- [x] Rebuild and recreate the backend, then verify the one-key `legacy` runtime keyring, health, readiness and database connectivity.
- [ ] Add production multi-key environment provisioning and a controlled re-encryption workflow before rotating stored credentials.
- [ ] Define old-key retirement, key escrow and backup-retention procedures.
- [x] Create and validate schema-only expand migration `0012_credential_keyring_expand` without credential backfill or runtime configuration changes.
- [x] Apply migration `0012_credential_keyring_expand` after explicit approval and verify its columns, constraints and ordered index while `provider_credentials` remains empty.
- [x] Create and validate contract migration `0013_credential_keyring_contract` with a fail-closed NULL-reference precondition and no backfill or decryption.
- [x] Apply and verify migration `0013_credential_keyring_contract` in the real development database while `provider_credentials` is empty.
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
