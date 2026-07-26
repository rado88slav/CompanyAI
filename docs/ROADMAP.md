# Company AI — Development Roadmap

## 1. Roadmap Goal

This roadmap defines the order in which the Company AI platform will be built.

The objective is to create the smallest useful MVP without adding unnecessary infrastructure.

Each phase must be completed, tested and documented before moving to the next one.

The initial MVP must provide:

- a central dashboard;
- a local AI agent;
- multiple-company-ready architecture;
- email platform management;
- phone platform management;
- task execution;
- approval controls;
- activity and audit history;
- portable installation through Docker and Bash scripts.

Current provider foundation status: Provider Connections, the dry-run-only Provider Execution foundation, the thin local-test email workflow, the first safe Agent Runtime vertical slice, deterministic mock email campaign listing and the first Lemlist read-only campaign adapter contract are implemented and verified with fake transports. The immutable keyring core and runtime support exist, and the real local keyring cutover is complete with active ID `legacy`. The repository and real development database heads are both `0014_email_workflow`; `0013_credential_keyring_contract` remains the verified keyring contract predecessor with `provider_credentials.encryption_key_id` as `VARCHAR(64) NOT NULL`. No credential backfill or re-encryption occurred. Dashboard Stage 1 provides the tested React, TypeScript and Vite shell, polished read-only operations homepage, authenticated company-scoped summary API, a production-quality read-only Activity Center, a read-only System Status page, a real protected Settings area with safe local preferences, built-in multilingual Documentation Center, a read-only Provider Connections module, mock email campaign view, a controlled Agent Activity page backed by deterministic internal tools, graphical administrator login/logout, authenticated session bootstrap and active company selection. A development-only idempotent activity seed command exists for local Activity Center visual testing. CompanyAI Local Edition Beta now has a production local runtime foundation, offline package builder, WSL2 lifecycle scripts, Windows wrappers, manual backup/restore foundation, setup-required dashboard wizard, single-use first-run CLI fallback and backend-enforced Email Sandbox policy. Production secret-manager provisioning, controlled re-encryption tooling, old-key retirement/key escrow, full workstation acceptance, live provider credentials and real pilot outreach remain open.

---

## 2. Development Rules

Every development phase follows this cycle:

1. Define the requirement.
2. Document the design.
3. Implement the smallest working version.
4. Test the implementation.
5. Record architectural decisions.
6. Update the built-in Documentation Center for any user-visible feature.
7. Update project progress and inventory.
8. Create or update the required Bash scripts.
9. Commit the completed phase to Git.

A phase is not complete only because the code starts.

It is complete when:

- the feature works;
- errors are handled;
- tests pass;
- documentation is updated;
- the built-in Documentation Center is updated for all user-visible changes;
- installation remains reproducible;
- no secrets are committed to Git.

---

# Phase 0 — Project Foundation

## Goal

Prepare a stable, portable and documented development environment.

## Tasks

- verify Windows, WSL2 and Ubuntu;
- configure Docker Desktop integration;
- test Docker Engine and Docker Compose;
- install and configure VS Code for WSL;
- create the repository structure;
- create project administration files;
- create the architecture document;
- create this roadmap;
- establish Bash script standards;
- prepare Git configuration;
- create the first repository commit.

## Bash scripts

- `scripts/setup.sh`
- `scripts/admin-setup.sh`
- future `scripts/init-git.sh`
- future `scripts/update-inventory.sh`
- future `scripts/health-check.sh`

## Completion criteria

- Docker containers can run without `sudo`;
- the project opens through VS Code in WSL;
- the repository structure exists;
- architecture and roadmap are documented;
- Git is initialized;
- the first commit is created;
- the project can be copied or cloned to another machine.

## Status

In progress.

---

# Phase 1 — Docker and Database Foundation

## Goal

Create the first working Docker Compose environment with PostgreSQL.

## Tasks

- define environment variables;
- improve `.env.example`;
- create the PostgreSQL service;
- create persistent database storage;
- add a database health check;
- create a basic backend container;
- create a basic agent container;
- create a basic dashboard container;
- define Docker networks;
- define startup dependencies;
- create start and stop scripts;
- verify clean startup and shutdown.

## Initial containers

- `postgres`
- `backend`
- `agent`
- `dashboard`

## Bash scripts

- `scripts/docker/start.sh`
- `scripts/docker/stop.sh`
- `scripts/docker/restart.sh`
- `scripts/docker/logs.sh`
- `scripts/docker/status.sh`
- `scripts/docker/reset-dev.sh`

## Completion criteria

- `docker compose up` starts all required services;
- PostgreSQL data persists after restart;
- every service has a health status;
- the system can be stopped and restarted safely;
- no manual container configuration is required;
- installation instructions are documented.

---

# Phase 2 — Backend API Foundation

## Goal

Create the central FastAPI backend and establish the internal project structure.

## Tasks

- create the FastAPI application;
- create application settings;
- configure structured logging;
- configure database access;
- configure SQLAlchemy;
- configure Alembic migrations;
- create API versioning;
- create standard API response formats;
- create error handling;
- create health and readiness endpoints;
- create initial automated tests.

## Initial endpoints

- `GET /api/v1/health`
- `GET /api/v1/readiness`
- `GET /api/v1/system/info`

## Backend modules

- configuration;
- database;
- models;
- schemas;
- services;
- repositories;
- API routes;
- security;
- logging;
- audit.

## Completion criteria

- the backend starts inside Docker;
- the backend connects to PostgreSQL;
- migrations run successfully;
- health endpoints return valid responses;
- tests run successfully;
- logs are readable and structured;
- application settings come from environment variables.

---

# Phase 3 — Company and Administration Core

## Goal

Implement the multi-company foundation before adding business integrations.

## Tasks

- create the company database model;
- create the administrator model;
- create company settings;
- implement active company context;
- ensure company-owned records are isolated;
- create company API endpoints;
- create audit log records;
- create initial development seed data;
- implement one local administrator account.

The Company Memberships and Roles foundation was committed as `d311521 Add company memberships and roles`. The Approval Manager foundation has been implemented ahead of its later integration phase and committed as `da9386c Add approval manager and authorization policies`; that commit was pushed to `origin/main`, and local `main`, `origin/main` and `origin/HEAD` were verified at `da9386c`. Migration `0007_approval_manager` is applied locally, and authenticated read-only listing is verified for requests, policies and usages. Safety defaults use the reserved `any` policy scope across concrete resource scopes without weakening `company_id` isolation. The first approved platform bootstrap ran before the backend image was rebuilt and created six legacy `company`/null policies plus six matching create audit events. Read-only verification detected the mismatch; the backend was rebuilt and the bootstrap was hardened. The explicitly approved controlled repair then atomically preserved the six legacy policies as revoked and created six active `any`/null replacements. Independent verification confirmed 12 policies, 12 create events, six revoke events and the strict one-active-policy-per-action invariant. Requests, decisions and usages remain empty, and no external runtime action was executed. Internal HTTP routes remain disabled until Agent Identity exists.

This historical documentation synchronization was completed in a later repository update.

The Agent Identity and Internal Agent Authentication foundation is committed as `201268b Add agent identity and internal authentication`. It introduces company-owned agents, one-time HMAC-protected machine credentials, short-lived separately signed agent JWTs, exact revocable permissions, lifecycle and audit management, administrator APIs and internal authentication endpoints. Static migration `0008_agent_identity` follows `0007` and is applied locally; at that foundation's verification point the real database was at `0008`, and all three agent tables contained zero rows. Backend Compose propagates all six Agent Authentication settings through tracked placeholders. Agent Runtime and provider integrations remain outside that foundation.

The Tool Registry foundation adds a non-executable global catalog, company enablement, authoritative historical agent grants, exact derived Approval Manager actions and a trusted in-process descriptor registry. Migration `0009_tool_registry` follows `0008` and is applied locally; at that foundation's verification point the real database was at `0009`, and all three Tool Registry tables contained zero rows. The rebuilt backend was healthy, readiness was verified, OpenAPI exposed 55 paths including all 14 Tool Registry paths, and invalid agent JWT access returned HTTP 401.

## Initial entities

- Company
- User
- CompanySetting
- AuditLog

## Initial company endpoints

- create company;
- list companies;
- read company;
- update company;
- activate company;
- view company activity.

## Completion criteria

- at least two test companies can exist;
- records from one company cannot be accessed through another company context;
- every company change is audited;
- the dashboard can identify the active company;
- the design does not assume only one company.

---

# Phase 4 — Dashboard Foundation

Stage 1 is implemented without deployment changes. The `frontend/` application
provides the shell, responsive navigation, graphical administrator login/logout,
authenticated session bootstrap, active company selector and a polished
operations homepage with health cards, company summary, recent activity, quick
actions and safe notifications. Typed runtime response validation and loading,
error, session-expired, backend-unavailable and empty states are present. The
read-only Dashboard Summary API supplies only safe service metadata,
company-scoped counts and a bounded recent audit subset. No email or call
integration, provider mutation, credential form, approval action or execution
control is present. The Provider Connections route reads the trusted provider
catalog and company-scoped connection metadata without rendering credential
values or exposing mutation controls. Production delivery, Activity Center and
System Status remain later dashboard work.

## Goal

Create the first usable web control center.

## Tasks

- initialize React, TypeScript and Vite;
- connect the dashboard to the backend API;
- create the main application layout;
- create navigation;
- create company selector;
- create system status page;
- create companies page;
- create activity center;
- create basic error display;
- create loading and empty states;
- prepare reusable UI components.

## Initial dashboard sections

- Overview
- Companies
- Tasks
- Integrations
- Email
- Phone
- Activity
- System
- Settings

## Completion criteria

- the dashboard runs in Docker;
- the dashboard communicates with the backend;
- the active company can be selected;
- system health is visible;
- backend errors are shown clearly;
- navigation works without page reloads.

---

# Phase 5 — Task and Agent Runtime

## Goal

Create the first controlled local agent capable of processing registered tasks.

## Tasks

- create the task database model;
- create task events;
- implement task state transitions;
- create task API endpoints;
- create the agent polling loop;
- create task claiming and locking;
- create the Tool Registry;
- create the first safe test tools;
- record every execution step;
- implement retry and timeout handling;
- display task progress in the dashboard.

## Initial task states

- `pending`
- `planning`
- `awaiting_approval`
- `approved`
- `running`
- `succeeded`
- `failed`
- `cancelled`

## Initial safe tools

- system health check;
- list registered tools;
- retrieve company information;
- create a test report;
- retrieve integration status.

## Completion criteria

- a task can be created from the dashboard;
- the local agent retrieves the task;
- the task is locked so it cannot run twice;
- the agent executes only registered tools;
- every state change creates an event;
- errors are stored and displayed;
- completed results appear in the dashboard.

---

# Phase 6 — AI Provider Integration

## Goal

Allow the agent to use a configurable AI model without depending permanently on one provider.

## Tasks

- define the AI provider interface;
- implement the OpenAI provider adapter;
- configure model selection;
- support structured responses;
- support tool selection;
- record token usage;
- record estimated cost;
- implement timeout and retry handling;
- create provider connection tests;
- prepare an interface for future providers.

## Initial provider

- OpenAI API

## Optional future providers

- Ollama;
- Azure OpenAI;
- Anthropic;
- Google;
- OpenAI-compatible providers.

## Important rule

Ollama is optional and must not be required for the first MVP.

## Completion criteria

- the model is selected through configuration;
- the agent can request a structured plan;
- AI output is validated before execution;
- invalid tool requests are rejected;
- token usage is recorded;
- changing the AI provider does not require changing core task logic.

---

# Phase 7 — Approval and Permission System

## Goal

Prevent the agent from performing sensitive actions without explicit authorization.

## Tasks

- create permission policies;
- create approval requests;
- create approval API endpoints;
- create approval dashboard screens;
- pause tasks awaiting approval;
- resume approved tasks;
- reject denied tasks;
- create approval expiration;
- record who approved or denied an action;
- audit every sensitive action.

## Initial action categories

### Read-only

Can normally run automatically.

### Reversible write

May require approval according to company policy.

### External or destructive

Requires approval by default.

## Completion criteria

- a task can pause before a sensitive action;
- the dashboard displays the requested action and parameters;
- the administrator can approve or reject it;
- the agent cannot bypass approval;
- every decision is stored in the audit log.

---

# Phase 8 — Integration Framework

## Goal

Create a provider-independent system for connecting external platforms.

## Tasks

- define the integration adapter contract;
- create integration records;
- create encrypted secret storage;
- create provider configuration schemas;
- implement connection testing;
- implement capability discovery;
- implement normalized errors;
- implement integration health status;
- create integration management pages;
- create test adapters.

## Initial integration categories

- email;
- phone;
- AI;
- future CRM.

## Completion criteria

- integrations are assigned to a company;
- credentials are never returned through normal API responses;
- connection tests work;
- health status is visible in the dashboard;
- providers expose normalized capabilities;
- provider-specific code stays inside adapters.

---

# Phase 9 — Email Platform Management

## Goal

Allow the platform to view and manage approved email operations.

## Initial scope

The first version will focus on management and visibility, not unrestricted autonomous campaigns.

## Tasks

- choose the first email provider;
- implement the email provider adapter;
- list connected email accounts;
- retrieve account status;
- retrieve campaign status when supported;
- retrieve replies when supported;
- create email drafts;
- require approval before sending;
- record email activity;
- display email status in the dashboard;
- normalize bounce and reply events.

## Candidate first providers

The first provider will be selected based on the company's actual campaign platform.
The first Lemlist read-only campaign adapter contract now exists behind the
provider abstraction and is verified with fake transport tests. A credentialed
live transport remains blocked until a real development credential is supplied
through the encrypted provider credential flow.

Possible options include:

- Microsoft 365;
- Google Workspace;
- Lemlist;
- Smartlead;
- Instantly;
- standard SMTP and IMAP where appropriate.

## Completion criteria

- the platform can test the email connection;
- connected accounts are visible;
- email activity is assigned to the correct company;
- the agent can create a draft;
- sending requires approval by default;
- external email actions are audited.

---

# Phase 10 — Phone Platform Management

## Goal

Allow the platform to view and manage approved phone operations.

## Tasks

- choose the first phone provider;
- implement the phone provider adapter;
- list phone numbers;
- retrieve call history;
- retrieve call status;
- retrieve transcripts;
- retrieve recordings when permitted;
- display call activity;
- create an outbound call request;
- require approval before starting a call;
- process provider webhooks;
- normalize call events.

## Candidate first providers

- Retell AI;
- Twilio;
- Telnyx.

The first implementation will likely use the platforms already selected by the company.

## Completion criteria

- the connection can be tested;
- available numbers are visible;
- call history is visible;
- transcripts are assigned to the correct company;
- outbound calls require approval by default;
- call actions and webhook events are audited.

---

# Phase 11 — Automation Engine

## Goal

Create controlled scheduled and event-based task creation.

## Tasks

- create automation rules;
- create schedules;
- create webhook-triggered rules;
- create automation run history;
- create pause and resume controls;
- prevent duplicate runs;
- create failure notifications;
- display automation activity;
- ensure automations create normal auditable tasks.

## Initial automation examples

- check for new email replies;
- update campaign statistics;
- retrieve completed call transcripts;
- create a daily activity summary;
- notify the administrator about failed integrations.

## Completion criteria

- schedules create tasks at the correct time;
- disabled rules do not run;
- duplicate execution is prevented;
- automation-created tasks use the normal approval system;
- every run is visible and auditable.

---

# Phase 12 — Backup, Restore and Portability

## Goal

Make it possible to move or recover the platform safely.

## Tasks

- create PostgreSQL backup scripts;
- create storage backup scripts;
- create configuration export;
- create restore scripts;
- create backup verification;
- create version compatibility checks;
- create installation documentation;
- test installation on a clean environment;
- test backup restoration.

## Bash scripts

- `scripts/backup/create.sh`
- `scripts/backup/verify.sh`
- `scripts/backup/restore.sh`
- `scripts/install/check-system.sh`
- `scripts/install/install.sh`
- `scripts/maintenance/health-check.sh`

## Completion criteria

- a backup can be created with one command;
- a backup can be verified;
- the system can be restored on another machine;
- credentials are handled securely;
- installation does not depend on undocumented manual steps.

---

# Phase 13 — MVP Stabilization

## Goal

Prepare the first useful internal release.

## Tasks

- complete end-to-end testing;
- perform security review;
- test company isolation;
- test approval bypass prevention;
- test integration failure handling;
- improve error messages;
- review logs;
- review database migrations;
- review backup and restore;
- prepare administrator documentation;
- prepare release notes;
- assign the first MVP version.

## MVP release target

`v0.1.0`

## Completion criteria

- all MVP features work together;
- critical tests pass;
- no secrets exist in Git history;
- backup and restore are tested;
- the platform runs after a clean installation;
- known limitations are documented;
- the system is ready for internal company use.

---

# Future Phases

The following capabilities are explicitly postponed until the MVP is stable:

- lead research agent;
- company discovery;
- email and phone discovery;
- document knowledge base;
- PDF and spreadsheet processing;
- vector search;
- CRM synchronization;
- advanced reporting;
- browser automation;
- multi-user role management;
- cloud deployment;
- local Ollama models;
- mobile interface;
- visual workflow builder;
- autonomous campaign execution.

These features will be planned separately and must not delay the initial MVP.

---

# Immediate Next Actions

After this roadmap is approved, the next steps are:

1. Verify Git availability.
2. Initialize the Git repository.
3. Improve `.gitignore`.
4. Create the first Git commit.
5. Organize the Bash script directories.
6. Create the Docker Compose foundation.
7. Start Phase 1.

---

# Current Project Status

Current phase:

**Phase 3 — Company and Administration Core: In Progress**

Completed foundations:

- Company management;
- Company Settings;
- administrator authentication;
- stateless Active Company Context.

Remaining in Phase 3:

- audit logging;
- repeatable development seed automation.
Provider Execution's dry-run architecture, persistence and Approval Manager integration are implemented and runtime-verified. Approval-required operations use evaluator decisions and atomic usage reservations; agent execution also requires an exact Tool Registry grant. Migration `0011_provider_execution` is an applied predecessor of current database head `0014_email_workflow`; the first local email E2E later created historical provider execution rows for the Local Test Email Provider only. Live adapters, real provider onboarding and external calls remain deferred pending explicit approval.

The first thin email workflow is implemented with applied schema migration
`0014_email_workflow`. It validates manual drafting, exact-content approval,
deterministic local test delivery, idempotency and safe auditing through the
Local Test Email Provider. Live mailbox import, AI drafting and real provider
sending remain Phase 9 work.
