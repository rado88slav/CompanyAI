# Generic SMTP/IMAP Provider — Codex Handoff

## Goal

Add support for standard company email mailboxes using SMTP for sending and IMAP for reading/replies.

Initial target mail server:

- Host: mail.agenturserver.de
- SMTP: 465 with SSL/TLS
- IMAP: 993 with SSL/TLS

The company currently has four existing mailboxes.

## Important repository findings

The project already contains:

- Provider Connections registry
- company-scoped provider connections
- encrypted provider credentials
- credential rotation and revocation
- provider activation/deactivation
- audit logging
- email capabilities
- existing email frontend pages
- provider execution architecture

Do not introduce a parallel credential or provider system.

## Existing relevant files

Backend:

- backend/app/core/provider_connections.py
- backend/app/services/provider_connection.py
- backend/app/schemas/provider_connection.py
- backend/app/api/routes/provider_connections.py
- backend/app/models/provider_connection.py
- backend/app/repositories/provider_connection.py

Frontend:

- frontend/src/pages/ProviderConnectionsPage.tsx
- frontend/src/api/providers.ts
- frontend/src/types/provider.ts

Prototype patch:

- project-admin/codex-handoff/generic-smtp-imap-prototype.patch

The prototype is for reference only. Inspect the current repository and implement according to existing architecture and conventions. Do not apply the patch blindly.

## Required provider

Recommended provider key:

generic_smtp_imap

Recommended display name:

Generic SMTP/IMAP

Category:

email

Capabilities:

- email.send
- email.read
- email.reply

## Configuration fields

Non-secret configuration:

- email_address
- sender_display_name
- username
- smtp_host
- smtp_port
- smtp_security
- imap_host
- imap_port
- imap_security
- imap_folder
- reply_to_address, optional

Secret fields:

- password

The password must use the existing encrypted ProviderCredential system.

## Security requirements

- Never return the password through the API.
- Never store the password in provider configuration.
- Never log the password.
- Never include authentication payloads in audit logs.
- Never display the password after saving.
- Validate TLS certificates.
- Do not provide an option to disable certificate validation.
- Use bounded connection and read timeouts.
- Avoid unbounded retries.
- Sanitize provider error messages before returning them to the frontend.
- Maintain company isolation.
- Revoked connections and credentials must not be usable.

## Connection testing

Implement separate SMTP and IMAP connection checks.

The test should verify:

SMTP:

- DNS/connectivity
- TLS negotiation
- authentication

IMAP:

- DNS/connectivity
- TLS negotiation
- authentication
- access to the configured root folder

The basic connection test must not send an email.

A later explicit test-email action may send only to an administrator-selected internal address.

## Activation behavior

A connection must not become active unless:

- an active credential exists;
- SMTP test succeeds;
- IMAP test succeeds.

Prefer retaining the existing ProviderConnection lifecycle unless a schema change is clearly justified.

Testing/error information may be stored as safe metadata or dedicated health data rather than adding status values casually.

## Initial UI scope

Provider Connections page should support:

- Add Generic SMTP/IMAP mailbox
- enter non-secret settings
- enter password securely
- test SMTP
- test IMAP
- save connection
- activate only after successful tests
- show connection health and last test time
- show safe error summaries
- never render credential values

Do not implement campaigns in this task.

## Phase 1 acceptance criteria

- Generic SMTP/IMAP appears in the trusted provider catalog.
- One mailbox can be configured.
- Password is encrypted using the current credential encryption service.
- Password is absent from API responses and logs.
- SMTP connectivity and login can be tested.
- IMAP connectivity and login can be tested.
- Failed tests prevent activation.
- Successful tests allow activation.
- Existing providers continue working.
- Backend tests pass.
- Frontend type-check/build passes.
- No unnecessary database migration is introduced.
- Documentation is updated.
- Changes are committed as one focused commit.

## Required backend tests

- provider descriptor is listed;
- unsupported configuration fields are rejected;
- password in configuration is rejected;
- missing password is rejected;
- password credential is encrypted;
- credential value is never returned;
- activation without credential fails;
- activation without successful connection tests fails;
- invalid SMTP login is handled safely;
- invalid IMAP login is handled safely;
- SMTP timeout is handled;
- IMAP timeout is handled;
- invalid TLS certificate is rejected;
- cross-company access is rejected;
- revoked connection cannot be resolved or used;
- sensitive values do not appear in audit logs.

## Required frontend checks

- email field validation;
- TCP port validation;
- masked password field;
- password is cleared after submission;
- understandable duplicate-slug error;
- failed SMTP test does not activate;
- failed IMAP test does not activate;
- successful connection appears as active;
- credential values are never rendered.

## Manual integration test

Use two controlled company mailboxes:

1. Configure Mailbox A.
2. Configure Mailbox B.
3. Test SMTP and IMAP for both.
4. Send one explicit test email from A to B.
5. Confirm B receives it.
6. Reply from B.
7. Confirm the reply can later be synchronized and associated with the original conversation.
8. Confirm no credential appears in browser responses, backend logs, audit logs, or frontend state inspection.

## Out of scope for Phase 1

- bulk campaigns;
- mailbox rotation;
- randomized timing;
- automatic inbox polling;
- background synchronization;
- bounce processing;
- unsubscribe processing;
- automatic replies;
- attachments;
- campaign analytics.

These belong to later phases.

## Later phases

Phase 2:

- single-message send;
- reply;
- sent-message record;
- attachments;
- audit events.

Phase 3:

- manual IMAP synchronization;
- incremental synchronization;
- threading;
- duplicate prevention;
- read/unread handling;
- attachment import.

Phase 4:

- approved campaigns;
- randomized send timing;
- hourly/daily limits;
- mailbox rotation;
- automatic pauses;
- bounce and unsubscribe handling;
- reply detection;
- Approval Manager integration.

## Execution instructions for Codex

1. Inspect current repository state first.
2. Read architecture and project-admin documentation.
3. Review the prototype patch only as a reference.
4. Produce an implementation plan before editing.
5. Reuse existing provider, credential, audit, authorization and email abstractions.
6. Avoid broad refactors unrelated to this provider.
7. Run the repository-standard backend and frontend validation commands.
8. Update project documentation and inventory if required by project conventions.
9. Present the final diff summary and test results.
10. Create one focused Git commit only after validation passes.
