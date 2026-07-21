# Project To-Do

## Current Phase

**Phase 1 — Docker and Database Foundation**

---

## Immediate Tasks

### 1. Environment Configuration

- [ ] Expand `.env.example`.
- [ ] Define project and environment variables.
- [ ] Define PostgreSQL database variables.
- [ ] Create a local `.env` file.
- [ ] Confirm that `.env` is ignored by Git.

### 2. PostgreSQL Container

- [ ] Add PostgreSQL to `docker-compose.yml`.
- [ ] Create a persistent PostgreSQL volume.
- [ ] Configure a database health check.
- [ ] Configure safe restart behavior.
- [ ] Test database startup.
- [ ] Test data persistence after container restart.

### 3. Backend Container Foundation

- [ ] Create the backend Dockerfile.
- [ ] Create the initial Python project files.
- [ ] Add a temporary backend health endpoint.
- [ ] Connect the backend container to PostgreSQL.
- [ ] Add a backend health check.

### 4. Agent Container Foundation

- [ ] Create the agent Dockerfile.
- [ ] Create the initial Python agent process.
- [ ] Add a temporary agent health mechanism.
- [ ] Connect the agent to PostgreSQL.
- [ ] Confirm that the agent container can restart safely.

### 5. Dashboard Container Foundation

- [ ] Initialize React, TypeScript and Vite.
- [ ] Create the dashboard Dockerfile.
- [ ] Add a temporary system status page.
- [ ] Expose the dashboard through a local port.
- [ ] Confirm that the dashboard container starts correctly.

### 6. Docker Compose Management

- [ ] Define the internal Docker network.
- [ ] Define container startup dependencies.
- [ ] Add service health checks.
- [ ] Verify clean startup of all containers.
- [ ] Verify clean shutdown of all containers.
- [ ] Verify restart behavior.

### 7. Bash Automation

- [ ] Create `scripts/docker/start.sh`.
- [ ] Create `scripts/docker/stop.sh`.
- [ ] Create `scripts/docker/restart.sh`.
- [ ] Create `scripts/docker/status.sh`.
- [ ] Create `scripts/docker/logs.sh`.
- [ ] Create `scripts/docker/reset-dev.sh`.
- [ ] Register descriptions in every new script.
- [ ] Update the automatic scripts index.

### 8. Documentation and Git

- [ ] Document local Docker startup.
- [ ] Document environment variables.
- [ ] Update `project-admin/progress.md`.
- [ ] Update the project inventory.
- [ ] Verify that no secrets are staged.
- [ ] Commit Phase 1 in logical Git commits.

---

## Phase 1 Completion Criteria

Phase 1 is complete when:

- [ ] PostgreSQL starts through Docker Compose.
- [ ] PostgreSQL data survives container restarts.
- [ ] Backend, agent and dashboard containers start.
- [ ] All required services expose health information.
- [ ] The full environment starts with one Bash command.
- [ ] The full environment stops with one Bash command.
- [ ] No undocumented manual configuration is required.
- [ ] Git working tree is clean.
- [ ] Documentation and inventory are current.

---

## Later Phases

- [ ] Phase 2 — Backend API Foundation
- [ ] Phase 3 — Company and Administration Core
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

2026-07-21