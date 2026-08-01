---
slug: getting-started
title: Getting Started
category: Basics
summary: Sign in, choose a company, move through the dashboard and end a session safely.
keywords: login, company, navigation, logout, session
related: dashboard,companies,security
---
# Getting Started
CompanyAI is a company-scoped operations dashboard. Start by signing in with an approved administrator account, then select the company you are allowed to work with.
## Steps
1. Open the dashboard and sign in.
2. Choose the active company from the top bar.
3. Use the sidebar to open Overview, Activity, System Status, Providers, Agent, Email, Approvals or Documentation.
4. Use the breadcrumb trail in the top bar to confirm where you are.
5. Use Logout when you leave the workstation.
> [!TIP] If a saved company is no longer available, CompanyAI selects the first company you can access.
> [!WARNING] Never share passwords, tokens or copied browser storage values.
## Common mistakes
- Working in the wrong company.
- Treating read-only pages as live provider controls.
- Leaving a shared development browser session open.
## Related pages
- Dashboard
- Companies
- Security

---
slug: dashboard
title: Dashboard
category: Operations
summary: Understand the operational control center and its read-only health signals.
keywords: overview, health, quick actions, notifications, operations
related: activity-center,system-status,providers
---
# Dashboard
The Overview page is the operational control center. It summarizes health, current company, providers, approvals, email visibility, agent status and recent activity.
## What to look at first
1. System Health shows backend, database, agent, providers, email and storage posture.
2. Company Summary confirms the selected company and key counts.
3. Quick Actions open common operational modules.
4. Recent Activity links to the full Activity Center.
> [!NOTE] Overview is intentionally read-only. It does not send email, launch campaigns or mutate providers.
## Best practices
- Refresh before reviewing a live local validation.
- Confirm the company name before opening a module.
- Use Activity Center for chronological evidence.

---
slug: companies
title: Companies
category: Administration
summary: Learn how active company context scopes all dashboard data.
keywords: company, membership, active company, isolation, selector
related: getting-started,security,activity-center
---
# Companies
Every operational record in CompanyAI belongs to a company. The active company selector controls which company-scoped records the dashboard requests.
## Steps
1. Sign in.
2. Open the company selector in the top bar.
3. Choose only from companies listed for your account.
4. Recheck page data after switching companies.
> [!WARNING] A stale or unauthorized company ID is rejected by the backend. The UI falls back to a safe accessible company.
## Best practices
- Verify the company before approvals or email workflow review.
- Use separate administrators for requester and approver flows.

---
slug: providers
title: Providers
category: Integrations
summary: Review provider connections, statuses and the current read-only integration model.
keywords: provider, connection, lemlist, credential, adapter, status
related: system-status,email-campaigns,security
---
# Providers
Providers are external or local adapters represented through safe company-scoped connection metadata. The Providers page shows configured connections and trusted provider types.
## Steps
1. Open Provider Connections.
2. Review configured and active connection counts.
3. Inspect authentication type and capabilities.
4. Use System Status to understand provider posture.
> [!INFO] Credential values are never rendered in the dashboard.
## Generic SMTP/IMAP mailbox
1. Select Add email mailbox.
2. Enter non-secret mailbox settings: email address, sender name, username, SMTP and IMAP hosts, ports, security modes and IMAP folder.
3. Enter the password only in the masked password field.
4. Save the mailbox, then run Test SMTP and Test IMAP.
5. Activate only after both tests succeed.
> [!WARNING] SMTP tests do not send email. IMAP tests open the configured folder read-only and do not modify messages.
## Troubleshooting
- DNS failure: check the host name.
- Connection failure or timeout: check port, firewall and network access.
- TLS failure: use a valid trusted certificate. Invalid certificates cannot be accepted.
- Authentication failure: check username and password without pasting secrets into logs.
- Folder not found: check the IMAP folder, usually INBOX.
## Common mistakes
- Expecting catalog entries to mean a live credential exists.
- Confusing mock/local providers with external delivery.

---
slug: agent
title: Agent
category: Automation
summary: Understand the safe read-only Agent Runtime and Tool Registry boundary.
keywords: agent, runtime, tool registry, read-only, audit, approval
related: approvals,activity-center,security
---
# Agent
The Agent page runs deterministic internal tools through a controlled runtime boundary. Tools are registered, company-enabled and audited.
## Steps
1. Open Agent Activity.
2. Enable the local read-only tool if it is not available.
3. Run a read-only tool.
4. Review the structured result and audit event.
> [!TIP] Agent Runtime has no unrestricted shell and no arbitrary external HTTP access.
> [!WARNING] High-risk future tools must stay behind approvals and exact permissions.
## Best practices
- Treat tool output as company-scoped evidence.
- Use Activity Center to review agent actions later.

---
slug: ai-agents
title: AI Agents
category: Automation
summary: Create the Email Operations Preview Agent and run safe synthetic tasks.
keywords: agent, manager, preview, prompt, openclaw, approval, synthetic
related: agent,approvals,email-automation
---
# AI Agents
AI Agents is the first product-level Agent Manager. Today it uses a deterministic local preview adapter. OpenClaw itself is not integrated.
## Steps
1. Open AI Agents.
2. Create the Email Operations Preview Agent from the built-in template.
3. Review the prompt preview before activation.
4. Activate the agent.
5. Run one of the synthetic preview tasks.
## Expected results
- Schedule preview and draft tasks return structured proposals.
- Unsubscribe classification recommends suppression.
- Campaign pause proposals show Approval Manager status.
- Forbidden send is denied.
> [!WARNING] No real email, provider execution, mailbox login or campaign launch is performed.
## OpenClaw
OpenClaw remains a future separate adapter contract with no Docker socket, no direct database access and no unrestricted filesystem.

---
slug: email-campaigns
title: Email Campaigns
category: Email
summary: Learn the mock and read-only email campaign model and the local test email workflow.
keywords: email, campaign, mock, lemlist, inbox, approval, send
related: approvals,providers,activity-center
---
# Email Campaigns
Email Operations currently supports local test email workflow evidence and mock/read-only campaign visibility. It does not send real email or launch real campaigns.
## Steps
1. Open Email Operations.
2. Review imported inbound email.
3. Open details for proposal and approval context.
4. Review mock campaign status and read-only counts.
> [!WARNING] Explicit local test send is deterministic and local-only. It is not external delivery.
## Best practices
- Confirm approval state before relying on an outbound snapshot.
- Use Providers to verify whether a live provider credential exists.

---
slug: email-automation
title: Email Automation
category: Email
summary: Configure preview-only campaign schedule policy before a worker exists.
keywords: email, automation, schedule, timezone, preview, mailbox, follow-up, approval
related: email-campaigns,providers,email-sandbox
---
# Email Automation
Email Automation stores company-specific campaign schedule policy and can preview planned send slots. It does not send email, create provider executions or run a background scheduler.
## Steps
1. Open Email Operations.
2. Set timezone, weekdays, send windows, randomized delays and limits.
3. Select Generic SMTP/IMAP mailboxes when they are active and healthy.
4. Save settings, then run a dry-run preview.
> [!WARNING] Worker execution is intentionally disabled. Preview output is planning evidence only.
## Best practices
- Keep approval mode conservative until real scheduler work is reviewed.
- Use pause when mailbox health or business timing is uncertain.

---
slug: approvals
title: Approvals
category: Governance
summary: Review approval requests, decision separation and immutable evidence.
keywords: approval, decision, requester, approver, immutable, policy
related: email-campaigns,agent,security
---
# Approvals
Approvals protect risky actions by separating request and decision. The dashboard shows exact approval content and decision actions when permitted.
## Steps
1. Open Approvals.
2. Read the exact requested action and content.
3. Confirm requester and approver are different administrators where required.
4. Approve or reject only when the content is correct.
> [!WARNING] Self-approval must remain blocked. Do not weaken this policy for convenience.
## Best practices
- Check immutable outbound snapshots after approval.
- Use Activity Center for the audit trail.

---
slug: activity-center
title: Activity Center
category: Operations
summary: Use the unified chronological timeline for agent, approval, provider and email events.
keywords: activity, timeline, audit, events, filters, details
related: dashboard,approvals,system-status
---
# Activity Center
Activity Center is the readable operational timeline. It normalizes audit events into cards with category, status, actor, source and safe details.
## Steps
1. Open Activity.
2. Filter by category or severity.
3. Expand safe details only when needed.
4. Open the related module for more context.
> [!INFO] Raw audit details, provider payloads and secret-like values are not shown.
## Best practices
- Use it for validation evidence.
- Pair it with System Status when investigating operational state.
## Development data
Development environments can populate Activity Center with deterministic sample events by running `scripts/dev/seed-activity.sh`. The command is development-only, company-scoped, idempotent and creates no credentials, provider calls or external delivery.

---
slug: system-status
title: System Status
category: Operations
summary: Read health indicators for backend, database, providers and planned services.
keywords: system, health, readiness, backend, database, lemlist, telephony
related: dashboard,providers,activity-center
---
# System Status
System Status is a health-indicator page. It reports current runtime posture and clearly marks planned or limited areas.
## Steps
1. Open System Status.
2. Check Backend and Database first.
3. Review Providers and Agent Runtime.
4. Treat Queue, Telephony and future AI Providers as planned unless marked healthy.
> [!NOTE] This page contains no mutation actions.
## Common mistakes
- Reading a planned service as a configured live integration.
- Ignoring provider status before investigating email visibility.

---
slug: security
title: Security
category: Governance
summary: Understand credential safety, permissions, approvals, audit and company isolation.
keywords: security, credentials, permissions, audit, tokens, secrets
related: approvals,companies,providers
---
# Security
CompanyAI is designed around company isolation, explicit authorization, safe credential storage and append-only audit evidence.
## Key rules
1. Credentials are not rendered in the dashboard.
2. Tokens must not be copied into tickets or documentation.
3. Company context is enforced by the backend.
4. Approval separation protects risky actions.
5. Audit events preserve evidence without secret payloads.
> [!WARNING] Do not add credential-entry forms unless the approved encrypted storage flow is used.
## Best practices
- Review permissions before enabling tools.
- Keep local development credentials separate from real accounts.

---
slug: settings
title: Settings
category: Help
summary: Manage local dashboard preferences, session actions and documentation shortcuts.
keywords: settings, preferences, theme, notifications, profile, language
related: getting-started,security,faq
---
# Settings
Settings is the protected workspace for account context and safe local dashboard preferences. It does not collect credentials or change passwords.
## Sections
1. Profile shows display name, email, role and active company.
2. Preferences stores interface language, documentation language, landing page, timezone, date format and density locally.
3. Appearance stores light, dark or system mode locally.
4. Notifications stores local preferences for approvals, provider health, campaigns and agent signals.
5. Security shows current session context and lets you log out.
6. Company defaults shows read-only company information and dashboard preference.
7. Documentation opens the built-in Documentation Center.
> [!WARNING] Dashboard password change and MFA require a future verified secure backend flow. For Local Edition administrator recovery, use only the documented interactive local CLI; do not type replacement passwords into any unsupported form, chat, command argument or environment variable.
## Best practices
- Save after changing preferences.
- Use Documentation language to keep help content aligned with your workflow.
- Treat settings as browser-local until backend preference storage exists.

---
slug: faq
title: FAQ
category: Help
summary: Practical answers for common CompanyAI usage questions.
keywords: faq, questions, troubleshooting, login, provider, email, agent
related: getting-started,security,system-status
---
# FAQ
## Why can I not see a company?
Your administrator account must have active access to that company, or you must be a platform superuser.
## Can CompanyAI send real email now?
No. Current email delivery is local test only, and campaign views are mock or read-only.
## Why is a provider listed but not active?
The trusted catalog can contain a provider type before a company connection or live credential exists.
## Where do I check what happened?
Use Activity Center for a readable timeline and Audit Log for low-level audit fields.
## What should I do if the session expires?
Sign in again. The dashboard clears protected context automatically.

---
slug: local-edition
title: Local Edition Beta
category: Operations
summary: Install and run CompanyAI locally on a Windows workstation.
keywords: local, beta, docker, windows, backup, sandbox, install
related: getting-started,system-status,settings
---
# Local Edition Beta
CompanyAI Local Edition Beta is designed for a Windows workstation with Docker Desktop and WSL2. The dashboard opens at `http://localhost:8080`.
## Essentials
1. Copy the package to the internal SSD before use.
2. Start with `scripts/local/start.sh` or the Windows Start wrapper.
3. Stop with `scripts/local/stop.sh`.
4. Back up with `scripts/local/backup.sh`.
5. Diagnose with `scripts/local/diagnose.sh`.
> [!WARNING] Do not run business data permanently from an ordinary USB flash drive.
## First run
If no administrator exists, the dashboard shows a setup-required wizard. Complete it once; no default password exists.
## Backups
Database backups are manual and checksum-protected. Optional encrypted configuration backup is available only when the operator supplies a passphrase for that command.
## Safety
LAN access is disabled by default, data lives in persistent Docker volumes, and normal stop, restart, rebuild and update commands preserve business data.

---
slug: email-sandbox
title: Email Sandbox
category: Email
summary: Understand the restricted email test mode for early controlled outreach validation.
keywords: email, sandbox, allowlist, approval, quota, emergency stop
related: email-campaigns,approvals,security
---
# Email Sandbox
Email Sandbox is the required safety boundary before any real-world outreach pilot. The backend enforces recipient allowlists, sender allowlists, quotas, approval, duplicate-send protection and the emergency stop.
## Initial limits
1. Only allowlisted team-controlled recipients.
2. One recipient per message.
3. Five messages per hour.
4. Ten messages per day.
5. `[COMPANYAI TEST]` subject prefix when configured.
6. No automatic follow-ups, bulk sending or attachments.
## Controlled single-message test
Email Operations can preview one Generic SMTP/IMAP test message, manage exact test recipients, request Approval Manager authorization, refresh approval status and run either simulation or an explicitly confirmed LIVE TEST. Any message edit invalidates the preview and approval state. Approvals shows the exact sender, recipient, subject, body, mode and idempotency reference for review; policy may require another authorized administrator. Allowlist audit records contain only operation metadata, changed state and recipient count. Simulation does not decrypt credentials, open SMTP or send email. LIVE TEST can send exactly one message after approval and final typed confirmation.
> [!WARNING] Do not use real HVAC prospects during sandbox acceptance testing.
## If a send is rejected
Check the visible reason, approval state, allowlist and emergency stop. Rejections are audited with sanitized reasons.

---
slug: release-notes
title: Release Notes
category: Product
summary: Track recent product-quality dashboard milestones.
keywords: release, notes, changes, activity, status, documentation
related: dashboard,activity-center,system-status
---
# Release Notes
## Current dashboard milestone
- Operations homepage polished into a control center.
- Activity Center added as a normalized read-only timeline.
- System Status added for health indicators only.
- Documentation Center added as a multilingual built-in help system.
- Breadcrumb navigation added to the protected dashboard shell.
- Settings added with safe local preference storage.
- Development activity seed command added for local Activity Center testing.
- Local Edition Beta foundation added with production runtime, lifecycle scripts, backup/restore foundation, setup-required detection and backend-enforced Email Sandbox policy.
## Safety posture
- No real email sends.
- No campaign launches.
- No phone calls.
- No paid external actions.
- No unrestricted shell or arbitrary HTTP tool access.
