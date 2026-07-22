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

- [ ] Add a company update schema.
- [ ] Add a company update repository operation.
- [ ] Add a company update service operation.
- [ ] Add `PATCH /api/v1/companies/{company_id}`.
- [ ] Add company activation.
- [ ] Add company deactivation.
- [ ] Add tests for updates and status changes.
- [ ] Decide whether company slugs may change after creation.

### 3. Company Settings

- [ ] Define the `CompanySetting` model.
- [ ] Define supported setting categories.
- [ ] Create a migration for company settings.
- [ ] Create settings repository and service layers.
- [ ] Create settings API endpoints.
- [ ] Ensure every setting belongs to exactly one company.
- [ ] Add company isolation tests.

### 4. Administrator Foundation

- [ ] Define the administrator or user model.
- [ ] Store passwords using a secure password hash.
- [ ] Create one local administrator account.
- [ ] Add a login endpoint.
- [ ] Add authenticated session or token handling.
- [ ] Protect administration endpoints.
- [ ] Add authentication tests.

### 5. Active Company Context

- [ ] Define how the active company is selected.
- [ ] Reject missing or invalid company context.
- [ ] Ensure company-owned records contain `company_id`.
- [ ] Prevent cross-company reads.
- [ ] Prevent cross-company writes.
- [ ] Add two-company isolation tests.
- [ ] Prepare the future dashboard company selector.

### 6. Audit Logging

- [ ] Define the `AuditLog` model.
- [ ] Record company creation.
- [ ] Record company updates.
- [ ] Record activation and deactivation.
- [ ] Record administrator actions.
- [ ] Create a company activity endpoint.
- [ ] Add audit log tests.

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
- [ ] Companies can be created, read, updated and activated.
- [ ] A local administrator can authenticate.
- [ ] Company settings are stored separately.
- [ ] Company-owned records are isolated.
- [ ] Cross-company access tests pass.
- [ ] Company changes create audit records.
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
