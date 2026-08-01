# Company AI — System Architecture

## 1. Purpose

Company AI is a local AI operations platform for managing business processes across multiple companies, products and external platforms.

The initial MVP focuses on:

- a central dashboard;
- a locally running AI agent;
- email platform management;
- phone platform management;
- task execution and activity history;
- support for multiple companies;
- portable installation through Docker and Bash scripts.

Future agents may handle:

- lead research;
- company discovery;
- email and phone discovery;
- CRM synchronization;
- document processing;
- automated reporting;
- campaign preparation;
- customer support.

---

## 2. Core Architectural Decision

The MVP will use a modular monolith architecture.

The platform will consist of several Docker containers, but the business logic will remain part of one coordinated application.

We will not begin with distributed microservices.

Reasons:

- simpler installation;
- easier debugging;
- lower infrastructure requirements;
- fewer networking and synchronization problems;
- easier backups;
- easier deployment to another machine;
- faster MVP development;
- modules can still be extracted into separate services later.

---

## 3. Main Components

The system contains the following main components:

### Dashboard

The dashboard is the human control center. Dashboard Stage 1 now provides a
desktop-first React, TypeScript and Vite application under `frontend/`, with
React Router navigation, a responsive accessible shell and a real read-only
Overview page. Agent, provider, email, calls, approvals, audit and settings
routes are explicit future-module placeholders and make no operational claims.

It allows the user to:

- manage companies;
- configure integrations;
- submit tasks;
- approve sensitive actions;
- review email activity;
- review phone activity;
- review agent activity;
- inspect logs and errors;
- view system health;
- manage prompts and configurations.

### Backend API

The backend is the central authority of the platform.

It is responsible for:

- API endpoints;
- authentication;
- company context;
- business rules;
- database access;
- task creation;
- approvals;
- integration configuration;
- webhook processing;
- audit logging;
- dashboard communication.

The backend will use FastAPI.

### Local Agent

The agent runs locally as a separate Docker container.

It is responsible for:

- retrieving pending tasks;
- planning task execution;
- selecting approved tools;
- calling AI model providers;
- using integration adapters;
- recording execution steps;
- returning structured results;
- stopping when approval is required.

The agent is local even when it uses a cloud AI model.

A local AI model is optional.

### Database

PostgreSQL will be the primary database.

It stores:

- companies;
- users;
- integrations;
- credentials metadata;
- tasks;
- task events;
- tool executions;
- approvals;
- prompts;
- conversations;
- campaigns;
- email activity;
- phone activity;
- audit logs.

PostgreSQL will also serve as the first task queue.

Redis will not be required for the initial MVP.

### Integration Layer

Every external platform must be accessed through an adapter.

Examples:

- Microsoft 365;
- Google Workspace;
- SMTP providers;
- Lemlist;
- Smartlead;
- Instantly;
- Retell AI;
- Twilio;
- Telnyx;
- future CRM platforms.

The core platform must not depend directly on a specific provider.

Provider Connections now supplies the metadata and encrypted-credential foundation for this layer. Built-in provider descriptors are registered only by trusted Python code. Database records cannot name executable implementations, imports, modules, callables or commands.

Company connection metadata and encrypted credential versions are isolated by explicit company identifiers and composite foreign keys. Credentials use AES-256-GCM with associated data binding the company, connection, credential, provider key and encryption version. Public APIs expose metadata only; plaintext decryption is reserved for a narrow trusted in-process resolver and is not connected to provider execution.

Generic SMTP/IMAP mailbox connections use the same Provider Connections and
encrypted Provider Credential boundary. The trusted descriptor key is
`generic_smtp_imap`, category `email`, with `email.send`, `email.read` and
`email.reply` capabilities. Non-secret mailbox settings live in connection
configuration: email address, sender display name, username, SMTP/IMAP hosts,
ports, security modes, IMAP folder and optional reply-to address. The mailbox
password is accepted only as a `ProviderCredential` secret field and must never
appear in configuration, metadata, logs, audit details, API responses,
frontend persisted state or repository files.

SMTP and IMAP connectivity tests are separate administrator-controlled
Provider Connection actions. They resolve the host, establish a bounded-timeout
connection, verify TLS certificates through the platform trust store,
authenticate and, for IMAP, select the configured folder read-only. They do not
send email and do not change, move, mark or delete messages. Safe health
metadata is stored under `metadata.generic_smtp_imap_health`, containing only
protocol status, test timestamp, safe category, safe message and activation
readiness. A Generic SMTP/IMAP connection cannot be activated unless an active
encrypted credential exists and the last SMTP and IMAP tests both succeeded.
This uses the existing `inactive`/`active`/`revoked` connection lifecycle and
requires no database migration.

Email campaign automation planning now has a preview-only settings foundation.
Company-owned, non-secret campaign schedule policy is persisted in
`company_settings` under `email_automation/campaign_schedule`. The policy
covers timezone, weekdays, send windows, randomized delays, campaign/company
and mailbox limits, mailbox rotation, paused mailboxes, follow-up steps,
start/end boundaries, approval mode and auto-pause thresholds. The planning
service only produces dry-run schedule slots and sanitized audit events. It
does not create provider executions, connect to mailboxes, send email or run a
background worker. A future worker must consume this policy through the same
company-isolated service boundary and Approval Manager contract.

AI Agent Manager now provides the first product-level agent control surface in
preview-only mode. It reuses Agent Identity for company-owned agents and exact
permissions, stores safe structured profile sections in agent metadata and
runs deterministic local preview tasks through backend code. Proposals are
validated, evaluated through Approval Manager where relevant, audited and
returned as structured responses. The preview runtime cannot send email,
create provider executions, read credentials, call external networks, access
the Docker socket, run shell commands or touch the database directly.
OpenClaw itself is not integrated; only a future adapter contract is
documented.

Migration `0010_provider_connections` is applied locally after `0009_tool_registry`. The provider tables exist and contain zero rows. Provider Execution now supplies a separately authorized dry-run foundation, while live external calls, OAuth flows and connectivity checks remain future work.

The development credential-encryption key was safely rotated while `provider_credentials` contained zero rows. Its cryptographic material was subsequently preserved during the atomic local cutover from standalone `CREDENTIAL_ENCRYPTION_KEY` to the active-ID plus secret-keyring contract. The active development key ID is the non-secret identifier `legacy`; the old standalone environment variable is no longer active. Secret values and hashes remain local and must never appear in Git, documentation, logs or configuration errors. The immutable keyring core exists, and the repository and real development database heads are both `0013_credential_keyring_contract`. The verified `encryption_key_id` contract is `VARCHAR(64) NOT NULL`; `provider_credentials` remains empty.

CompanyAI Local Edition Beta adds a separate production-local runtime for the
real HVAC workstation path. `docker-compose.local.yml` uses Nginx as the single
localhost entry point on `127.0.0.1:8080`, serves the production React build,
proxies `/api` to FastAPI, runs Alembic through a dedicated migration service
before backend readiness and keeps PostgreSQL unexposed to the host. Named
local volumes preserve PostgreSQL data, backups, logs and config across normal
stop, restart, rebuild, update and container uninstall operations.

The Local Edition lifecycle is script-driven through `scripts/local/` and
Windows PowerShell wrappers under `installer/windows/`. Offline package
creation exports Docker images with manifests and checksums while excluding
source-control history, generated secrets, `.env.local`, provider credentials
and `node_modules`. Backup and restore are manual, checksum-verified and
guarded by explicit restore confirmation.

Outbound email remains restricted. The backend Email Sandbox policy is enforced
inside the existing approved email reply send path; the dashboard is not the
authority. Local production send attempts check exact recipient and sender
allowlists, approval state, provider connection, duplicate-send protection,
quotas, subject prefix and emergency stop before provider execution. Rejected
attempts are audited with sanitized reason codes.

Provider Credential model, repository and service integration are keyring-aware. The repository runtime contract now requires `CREDENTIAL_ENCRYPTION_ACTIVE_KEY_ID` plus secret `CREDENTIAL_ENCRYPTION_KEYRING` JSON. Application creation parses the complete immutable keyring once before FastAPI is constructed and shares it with Provider Connections through application state. Standalone `CREDENTIAL_ENCRYPTION_KEY` and ambiguous mixed legacy/new configuration are rejected without fallback. New credentials and business rotations use encryption version 2, store the configured active key ID and revision `0`, and authenticate the key ID together with the existing company, connection, credential and provider identity. Previous configured keys are decryption-only because encryption always selects the active key.

Historical version-1 rows retain their original AAD. NULL key IDs are readable only when the configured keyring contains the explicit `legacy` entry; the active key is never guessed. Stored v1/v2 key IDs are resolved through the keyring, reads never mutate historical rows, and missing, malformed or unknown key IDs fail closed with sanitized errors.

The real local development runtime cutover is complete. The environment file was converted atomically while preserving its other entries and `600` permissions, the backend image was rebuilt, and the backend container was force-recreated without database changes. Runtime validation confirmed a one-key keyring whose configured and active IDs both equal `legacy`; health and database readiness return HTTP 200 with reachable database connectivity. No database row, credential, approval or execution was created or modified.

Migration `0013_credential_keyring_contract` is applied and verified in the real development database. Its fail-closed NULL precondition passed because `provider_credentials` contained zero rows, and the migration then made `encryption_key_id` mandatory without backfill, decryption or re-encryption. The backend image rebuild and container recreation with migration 0013 are complete, and the runtime keyring cutover remains healthy and active. Mandatory credential-keyring backend work blocking initial dashboard development is complete, and the first read-only dashboard foundation is implemented. Production secret-manager/keyring provisioning, controlled re-encryption tooling, old-key retirement and key escrow policy, and backup-retention procedures remain future security and operational work. `scripts/setup/create-env.sh --force` replaces the entire `.env` and must not be used for key-only rotation.

The authenticated company-scoped Dashboard Summary API is available at
`GET /api/v1/companies/{company_id}/dashboard/summary`. It requires the
existing activity, provider, approval and provider-execution read permissions.
One aggregate statement returns company counts and one bounded query returns
the five newest audit events ordered by creation time and ID. Explicit response
schemas exclude audit details, credential identifiers and material, encrypted
payloads, nonces, key IDs, keyring metadata, hashes and tokens. The endpoint
performs no writes, credential decryption, provider execution or external call.

After a local development terminal exposure, `APP_SECRET_KEY`, `AGENT_JWT_SECRET`, `AGENT_CREDENTIAL_PEPPER`, `CREDENTIAL_ENCRYPTION_KEY` and `POSTGRES_PASSWORD` were rotated without displaying their replacements. Both credential tables were empty beforehand. The local environment file and PostgreSQL role password were updated consistently, and backend health plus database readiness were verified afterward without modifying application rows. Secret values do not belong in Git or documentation; production secret management remains open.

### Tool Registry

The Tool Registry defines every action the agent may perform.

Example tools:

- list email accounts;
- read email;
- create email draft;
- send approved email;
- retrieve call history;
- initiate approved call;
- check campaign status;
- execute an approved Bash script;
- generate a report.

Each tool defines:

- name;
- description;
- input schema;
- output schema;
- required permissions;
- approval policy;
- integration provider;
- timeout;
- retry policy.

### Automation Engine

The Automation Engine creates tasks from schedules, events and rules.

Examples:

- check replies every morning;
- create a follow-up task;
- process an incoming webhook;
- summarize completed calls;
- update campaign statistics;
- notify the user about errors.

The initial version will use database schedules and a polling worker.

A more advanced queue or scheduler may be added later.

---

## 4. High-Level Data Flow

### Human-Initiated Task

1. The user submits a task from the dashboard.
2. The backend validates the request.
3. The backend assigns the active company context.
4. A task record is created in PostgreSQL.
5. The local agent retrieves the task.
6. The agent selects tools from the Tool Registry.
7. Sensitive actions request approval.
8. Approved actions are executed through integration adapters.
9. Results and execution steps are stored.
10. The dashboard displays the final status.

### Incoming Platform Event

1. An external platform sends a webhook.
2. The backend verifies the webhook.
3. The payload is normalized into an internal event.
4. The event is stored.
5. An automation rule may create a new task.
6. The agent processes the task.
7. The result is recorded and displayed.

---

## 5. Task State Model

Every agent operation must be represented as a task.

Supported task states:

- `pending`
- `planning`
- `awaiting_approval`
- `approved`
- `running`
- `succeeded`
- `failed`
- `cancelled`

A task must contain:

- task ID;
- company ID;
- task type;
- user request;
- structured input;
- current state;
- priority;
- assigned agent;
- creation time;
- start time;
- completion time;
- result;
- error information.

Every state change must create a task event.

---

## 6. Multi-Company Design

The platform must support multiple companies from the beginning.

Every business record must belong to a company.

Examples:

- integrations;
- email accounts;
- phone numbers;
- contacts;
- campaigns;
- tasks;
- prompts;
- documents;
- activity logs.

The backend must resolve company context before accessing business data.

The agent must never receive credentials or data from another company.

The first installation may contain only one company, but the database and application design must not assume this permanently.

---

## 7. Integration Adapter Contract

Every integration adapter must expose a consistent interface.

An adapter must provide:

- provider name;
- supported capabilities;
- connection test;
- credential validation;
- normalized errors;
- rate-limit handling;
- health status;
- structured input and output.

Example email capabilities:

- `email.accounts.list`
- `email.messages.read`
- `email.drafts.create`
- `email.messages.send`
- `email.campaigns.read`
- `email.replies.read`

Example phone capabilities:

- `phone.numbers.list`
- `phone.calls.create`
- `phone.calls.read`
- `phone.transcripts.read`
- `phone.recordings.read`

Provider-specific code must remain inside the adapter.

---

## 8. AI Provider Abstraction

The agent must not depend directly on one AI provider.

The AI provider interface will support:

- text generation;
- structured output;
- tool calling;
- image understanding when supported;
- token and cost reporting;
- timeout handling;
- retry handling.

Initial provider:

- OpenAI API

Possible future providers:

- Ollama;
- Azure OpenAI;
- Anthropic;
- Google;
- other OpenAI-compatible APIs.

The selected provider and model must be configurable.

---

## 9. Agent Runtime

The Agent Runtime contains:

### Task Runner

Retrieves and processes tasks.

### Planner

Converts a user request into execution steps.

### Tool Manager

Finds and validates available tools.

### Company Context

Restricts data, credentials and prompts to one company.

### Permission Engine

Determines whether a tool may run automatically.

### Approval Manager

Pauses tasks that require human approval.

### Model Provider

Communicates with the selected AI model.

### Execution Recorder

Records every important step and result.

### Error Handler

Classifies errors and applies retry policies.

The agent must not execute arbitrary commands generated by the AI model.

---

## 10. Bash Script Execution

Bash scripts are part of the platform's portability and administration strategy.

They will be used for:

- installation;
- initial setup;
- Docker management;
- backups;
- restoration;
- updates;
- health checks;
- maintenance;
- deployment.

The agent may execute only registered scripts from an allowlist.

The agent must not execute unrestricted shell text.

Each registered script must define:

- script name;
- purpose;
- allowed parameters;
- required permission;
- timeout;
- expected output;
- whether approval is required.

Scripts must be:

- idempotent when possible;
- non-interactive when used by automation;
- safe to run repeatedly;
- independent from the current working directory;
- compatible with Ubuntu under WSL2 and Linux servers;
- free of hardcoded credentials.

---

## 11. Approval and Safety Model

Actions are divided into three categories.

### Read-Only

May normally run automatically.

Examples:

- read campaign statistics;
- list calls;
- retrieve transcripts;
- check system health.

### Reversible Write

May require approval depending on company policy.

Examples:

- create an email draft;
- update an internal task;
- add a contact.

### External or Destructive

Require approval by default.

Examples:

- send an email;
- start a phone call;
- delete data;
- change credentials;
- launch a campaign;
- execute a maintenance script;
- modify integration settings.

Every approved action must be recorded in the audit log.

---

## 12. Credential Management

Secrets must never be stored in Git.

Examples:

- API keys;
- OAuth tokens;
- SMTP passwords;
- webhook secrets;
- encryption keys.

During the MVP, secrets may be stored in encrypted form in the database.

The master encryption key will be provided through an environment variable.

The `.env` file must remain local and excluded from Git.

The local development keyring is securely configured with active ID `legacy`. Backend application creation validates the active ID and complete keyring before FastAPI can report healthy or ready. Every encoded key must be exactly 64 hexadecimal ASCII characters or exactly 44-character padded Base64/Base64url decoding to exactly 32 bytes; standalone or mixed legacy configuration is rejected, and failures use a deterministic sanitized error.

The local development runtime uses the active-ID plus keyring contract with active ID `legacy`. Contract migration `0013_credential_keyring_contract` is applied and verified, so mandatory credential-keyring backend work blocking initial dashboard development is complete. Production deployments still require dedicated secret-manager/keyring provisioning; controlled re-encryption, old-key retirement and key escrow, and backup-retention procedures remain future work.

Do not use `scripts/setup/create-env.sh --force` for key-only rotation because it replaces the entire `.env` file.

---

## 13. Repository Structure

The current repository structure is:

```text
company-ai/
├── agent/
├── backend/
├── config/
├── frontend/
├── database/
├── docker/
├── docs/
├── integrations/
├── project-admin/
├── scripts/
├── storage/
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
Responsibilities:

### `agent/`

Local agent runtime, planning, tools and task execution.

### `backend/`

FastAPI application, business logic and API endpoints.

### `frontend/`

React, TypeScript and Vite dashboard source code.

### `integrations/`

External platform adapters.

### `database/`

Database migrations, initialization and development data.

### `config/`

Configuration templates and non-secret defaults.

### `docker/`

Dockerfiles and container-specific configuration.

### `scripts/`

Installation, development, deployment and maintenance scripts.

### `storage/`

Persistent runtime files, exports, reports, backups and uploads.

### `docs/`

Technical and operational documentation.

### `project-admin/`

Project progress, decisions, inventory and internal administration.

---

## 14. Approval Manager Boundary

Approval requests, immutable decisions, authorization policies and the usage reservation ledger are separate persistence concerns. Human APIs use Bearer authentication, Active Company Context and centralized company permissions. Runtime evaluation and reservation are internal Python services; no internal HTTP router is registered before Agent Identity exists.

Evaluation applies platform risk floors, block and always-require rules before selecting exactly one deterministic allow policy. Reservations lock that policy and persist usage plus audit data atomically. Provider side effects remain outside the database transaction and require future provider idempotency and reconciliation.

Authorization policies reserve `scope_type = any` as a resource-scope wildcard and require its `scope_id` to be null. Runtime actions and approval requests always use concrete scopes. The wildcard does not cross company boundaries: company policies remain filtered by `company_id`, while platform policies remain platform-wide. Exact scope IDs rank above exact scope types, which rank above `any`.

Safety bootstrap idempotence requires a complete match of every security-relevant policy field. Conflicting active policies are never silently widened, narrowed or replaced. The separately gated `--repair-legacy-scope` operation accepts only the exact former bootstrap shape, then revokes and replaces all eligible definitions with corresponding audit events in one transaction. It preserves all historical policies and audit records.

The first approved platform bootstrap ran from a stale backend image and created six legacy `company`/null platform policies. After read-only detection, container rebuild and bootstrap hardening, the user approved the controlled repair. It atomically preserved those six policies as revoked and created six active `any`/null replacements. Independent verification confirmed 12 policies total, 12 create audit events, six revoke audit events, exactly one valid active policy per safety action and no duplicate active bootstrap policies. No policy or historical audit event was deleted and no external action was executed. A further real bootstrap run has not been used to test post-repair idempotence.

The Company Memberships and Roles foundation is recorded in commit `d311521 Add company memberships and roles`. Approval Manager and Authorization Policies is recorded in commit `da9386c Add approval manager and authorization policies`, which was pushed to `origin/main`. Local `main`, `origin/main` and `origin/HEAD` were verified at `da9386c` with a clean working tree immediately after the push. Later documentation synchronization is tracked as a separate working-tree change until reviewed and committed.

Randomized sending cadence is not authorization logic and belongs to the future Campaign Scheduler.

## 15. Agent Identity Boundary

Agents are company-owned machine identities, never administrators. Machine credentials use a versioned public lookup ID plus a high-entropy secret. Only an HMAC-SHA256 digest keyed by the environment-only `AGENT_CREDENTIAL_PEPPER` is stored; plaintext is returned once after creation or rotation. Agent JWTs use dedicated secret, algorithm, issuer, audience and short TTL configuration and cannot authenticate through administrator dependencies.

Every agent JWT request revalidates the active company, agent status, agent `auth_version`, credential ownership, status and expiry from PostgreSQL. Exact permission keys remain database-authoritative and immediately revocable; no permission wildcard or provider capability is introduced here. Agent, credential and permission mutations preserve history and share one transaction with their audit events. Credential rotation lineage is enforced by a composite database relationship, so a rotated credential can reference only a predecessor owned by the same company and agent.

Migration `0008_agent_identity` creates the three agent tables, adds agent audit actors and connects Approval Manager's deferred agent identifiers with `ON DELETE RESTRICT` foreign keys. It is applied locally; at that foundation's verification point `agents`, `agent_credentials` and `agent_permissions` each contained zero rows. Backend Compose passes the dedicated credential pepper and agent JWT settings only through environment placeholders. The rebuilt backend verification confirmed invalid agent JWT responses returned HTTP 401. Retell agents remain external voice executors managed by Company AI rather than replacements for internal Agent Identity.

## 16. Tool Registry Boundary

The Tool Registry stores global tool metadata, company availability and historical agent grants. Database rows never contain Python import paths, handlers, source code, commands, credentials or executable payloads. Tool keys are exact lowercase dotted identifiers, and high or critical risk definitions always require approval.

`agent_tool_grants` is authoritative for agent-to-tool access and remains independent from `agent_permissions`. Composite foreign keys bind grants to the same company-owned agent and company tool record. Effective access is recalculated from current tool, company-tool, grant, company, agent and credential state, so disablement and revocation are immediate without deleting history.

A separate trusted in-process descriptor registry may receive callable references directly from application code. Database access and trusted runtime registration are both required for future execution, but this foundation exposes no execution endpoint, dynamic import, provider call, shell command or external side effect. Approval Manager action keys are derived as `tool.execute.<persisted-tool-key>` from authenticated agent identity.

Static migration `0009_tool_registry` follows `0008_agent_identity` and is applied locally. At that foundation's verification point the real database was at `0009_tool_registry`; `tool_definitions`, `company_tools` and `agent_tool_grants` existed and each contained zero rows. The rebuilt backend was healthy, readiness confirmed database reachability, OpenAPI exposed 55 paths including all 14 Tool Registry paths, and invalid agent JWT access to `/api/v1/internal/tools` returned HTTP 401.

## 17. Docker Architecture

The initial Docker Compose environment will contain:

- `backend`
- `agent`
- `dashboard`
- `postgres`

Possible later services:

- `redis`
- `reverse-proxy`
- `ollama`
- `object-storage`
- `monitoring`

The MVP must not require optional services.

The same repository and scripts should support:

- Windows with WSL2 and Docker Desktop;
- a Linux workstation;
- a Linux server.

---

## 16. Initial Technology Stack

### Backend

- Python
- FastAPI
- SQLAlchemy
- Alembic
- Pydantic

### Database

- PostgreSQL

### Agent

- Python
- configurable AI provider
- structured tool calling
- database-backed task processing

### Dashboard

- React
- TypeScript
- Vite

### Infrastructure

- Docker
- Docker Compose
- Bash

### Testing

- Pytest
- API integration tests
- adapter contract tests

---

## 17. MVP Boundaries

The first MVP will include:

- one administrator;
- multiple-company-ready data design;
- company management;
- integration configuration;
- email platform status;
- phone platform status;
- manual task creation;
- local agent task execution;
- approval workflow;
- task history;
- activity and audit logs;
- system health dashboard.

The first MVP will not include:

- unrestricted autonomous operation;
- visual workflow builder;
- complex CRM;
- lead scraping;
- full document knowledge base;
- advanced vector search;
- distributed microservices;
- Kubernetes;
- unrestricted browser automation;
- unrestricted shell access.

These may be added in later phases.

---

## 18. Development Principles

1. Build the smallest useful version first.
2. Keep modules replaceable.
3. Prefer official APIs over browser automation.
4. Never hardcode provider-specific logic in the core.
5. Never store secrets in source control.
6. Every task must be observable.
7. Every external action must be auditable.
8. Dangerous actions require approval.
9. Every business record belongs to a company.
10. Installation and maintenance must be scriptable.
11. Scripts must support migration to another machine.
12. Avoid infrastructure that the MVP does not need.
13. Add complexity only when a real requirement demands it.

---

## 19. Future Evolution

The modular monolith may later evolve by extracting individual modules.

Possible future services:

- dedicated automation service;
- dedicated webhook service;
- dedicated campaign service;
- dedicated document processing service;
- dedicated lead research agent;
- dedicated reporting service;
- dedicated notification service.

Extraction will happen only when scale, security or independent deployment requires it.

---

## 20. Primary System Flow

```text
User
  |
  v
Dashboard
  |
  v
Backend API
  |
  +----> PostgreSQL
  |
  v
Task Queue
  |
  v
Local Agent
  |
  v
Tool Registry
  |
  v
Integration Adapter
  |
  v
External Platform
  |
  v
Result / Webhook / Audit Log
```

---

## 21. Final Architectural Rule

The AI model may recommend actions.

The platform controls which actions are actually allowed.

The agent must operate through:

- registered tools;
- company context;
- permission rules;
- human approvals;
- complete audit logging.
Provider Execution is a dry-run-only foundation. It uses trusted operation descriptors, company-scoped execution and attempt history, explicit lifecycle states, sanitized payloads and fail-closed live adapters. Approval-required execution reuses the existing Authorization Evaluator and Authorization Usage ledger: the authenticated administrator or agent, exact operation/tool identifier, company scope and provider connection must match an active allow policy, and reservation occurs before an attempt starts. Agents additionally require an exact active Tool Registry grant. Authorization usage finalization, execution state, attempt history and audit events are committed atomically.

Migration `0011_provider_execution` is an applied predecessor of current database head `0013_credential_keyring_contract`. PostgreSQL verification confirmed both execution tables and their restrictive foreign keys, checks, uniqueness constraints and indexes; both tables contain zero rows. The rebuilt backend is healthy and database-ready. Authenticated checks return 22 operations across 8 providers and an empty company-scoped execution page, while OpenAPI exposes 74 total paths including 9 Provider Execution paths. No real provider credential, approval, execution or attempt was created, and no external provider call was made.

## Thin email workflow

The development-only vertical slice is test import → normalized inbound email
→ manual proposal → exact SHA-256 approval binding → explicit deterministic
test delivery → audit. States progress from received/draft through
awaiting-approval and approved/rejected to sent/send-failed. Editing stops after
submission and unique outbound/execution identities prevent duplicate delivery.

The Local Test Email Provider makes no network call and sends no real email.
Audit details exclude bodies and credentials. AI generation, live provider
authentication, HTML, attachments and bulk workflows are not implemented.

Local browser validation uses a development session setup screen in the
dashboard. It stores an administrator bearer token and active company UUID only
in `sessionStorage`, hides the token after save, provides a clear action and
does not bypass backend authentication, role permissions or approval checks.

`POST /api/v1/companies/{company_id}/provider-connections/local-test-email/setup`
is the only purpose-built Local Test Email Provider setup path. It is
administrator-authenticated, company-scoped, requires provider-management
permission, accepts no credential payload, creates no credential record, is
idempotent and fails closed outside development/test environments.

The first approved local development E2E validation completed against the
running application and real development database at `0014_email_workflow`. It
created reserved `example.test` evidence for one inbound message, one reply
proposal, one approval, one explicit local test send, one provider execution
and one attempt. Duplicate import and duplicate send protection were verified.
No live provider, real email address, credential, secret or external email
delivery was used.
