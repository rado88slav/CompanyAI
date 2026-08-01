# Live Single-Message SMTP Test

This guide covers the first approval-gated LIVE TEST path for exactly one
plain-text SMTP message through an active Generic SMTP/IMAP mailbox.

Do not paste mailbox passwords, personal recipient addresses, browser storage,
tokens or provider credentials into tickets, chat, shell commands or repository
files.

## Prerequisites

1. Local Edition is healthy.
2. A Generic SMTP/IMAP connection is active.
3. Password status is configured.
4. SMTP and IMAP tests both succeeded after the latest mailbox settings or
   credential change.
5. The active mailbox sender is present in the exact sender allowlist.
6. Email Sandbox emergency stop is disabled only for the controlled test
   window.
7. Company/mailbox quotas and working-hours policy allow the action.
8. Approval Manager policy still requires approval for provider execution.
9. If two-person approval is required, a second authorized administrator must
   approve the request. Do not create a hidden single-administrator bypass.

## Exact Allowlists

Before live execution, add:

- the active mailbox sender through Email Operations → Email Sandbox → Allow
  active mailbox sender, or as one exact sender address;
- the operator-controlled personal recipient address through Email Operations
  → One Test Email → Exact recipient allowlist.

Only exact email addresses are valid. Domains and wildcards are rejected for
senders and recipients. Do not record personal addresses in Git,
documentation, screenshots or tickets. Allowlist add and remove actions update
the company Email Sandbox policy and write sanitized audit metadata only:
operation name, changed flag and sender/recipient count. Audit records must not
contain addresses.

## Emergency Stop

The Email Sandbox panel shows emergency stop as `ACTIVE` or `INACTIVE`.
Disabling it requires an authorized administrator to type
`DISABLE EMAIL EMERGENCY STOP`. This makes approved LIVE TEST email possible
for the controlled test window. Re-enable the stop immediately after the test
or whenever the operator is not intentionally preparing a live one-message
send. Simulation remains available while the stop is active.

## Compose

Use LIVE TEST mode only for a harmless message:

- one active mailbox as From;
- exactly one manually entered To recipient;
- no CC or BCC;
- no recipient list;
- no attachments;
- no tracking;
- no links added automatically;
- no follow-up;
- subject starts with `[COMPANYAI TEST]`;
- plain-text body only.

## Approval And Confirmation

Use the normal flow:

1. Preview one message.
2. Review the visible preview status, sender, recipient, subject, body, digest,
   idempotency key and policy checks.
3. Request approval.
4. Open Approvals and review sender, recipient, subject and body.
5. Have another authorized administrator approve the request when self-approval
   is blocked by policy.
6. Return to Email Operations and refresh approval status.
7. Type the exact phrase `SEND ONE TEST EMAIL`.
8. Stop here unless the operator intentionally wants to execute the real
   one-message SMTP LIVE TEST.

The backend records execution state before contacting SMTP and uses the unique
idempotency key to prevent an intentional duplicate send. There are no
automatic retries.

## Results

`succeeded` means the SMTP server accepted the message. It does not prove inbox
delivery.

`failed_before_send` means the backend did not reach SMTP message acceptance.
Review the sanitized category and fix the prerequisite before creating a new
approved execution.

`outcome_uncertain` means the connection was lost during DATA or at a point
where server acceptance cannot be proven. Do not retry automatically. Review
the mailbox and audit trail before deciding whether a new one-message approval
is appropriate.

## Audit

Verify Activity Center for sanitized provider execution and single-message
events. Audit details may include operation key, execution mode, safe status,
message digest and policy/usage identifiers. They must not include passwords,
credential key identifiers, authentication details, full body or sensitive
headers.

## Disable LIVE Mode

After the test:

1. Re-enable Email Sandbox emergency stop if that is the local safety posture.
2. Remove the personal recipient from the exact allowlist when no longer
   needed.
3. Keep campaign, scheduler and follow-up controls disabled until a separate
   production review approves them.
