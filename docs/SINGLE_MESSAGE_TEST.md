# Controlled Single-Message Test

This guide covers the first approval-gated one-message test. It is prepared in
the application, but development and automated tests execute simulation only.

Prerequisites:

1. One Generic SMTP/IMAP mailbox exists.
2. The mailbox has one active encrypted credential.
3. Test SMTP succeeded.
4. Test IMAP succeeded.
5. The mailbox is active.
6. `email_sandbox/policy` contains the exact sender and recipient allowlists.
7. Emergency stop is disabled only for the short test window.

Dashboard sequence:

1. Open Email Operations.
2. Use One Test Email.
3. Select one active Generic SMTP/IMAP mailbox.
4. Enter exactly one recipient.
5. Keep the subject prefixed with `[COMPANYAI TEST]`.
6. Enter the plain-text body.
7. Use a unique idempotency key for this exact attempt.
8. Click Preview one message.
9. Verify sender, recipient, subject, body and digest.
10. Click Request approval.
11. Have a different authorized administrator approve the Approval Manager
    request.
12. Return to Email Operations and click Execute simulation.

Current behavior:

- Provider Execution records are dry-run only.
- The dashboard and backend label the flow as simulation only.
- No SMTP connection is opened by the send flow.
- No provider credential is decrypted by the send flow.
- No external email is sent.
- CC, BCC, attachments, tracking, follow-ups and recipient lists are not
  accepted by the schema.
- Duplicate idempotency keys are rejected.
- Missing approval is rejected.
- Sandbox rejections are audited with sanitized reason codes.

Rollback and stop:

- Use the Email Sandbox emergency stop before any live send test.
- Deactivate the mailbox or revoke its credential to block future attempts.
- Cancel pending approval requests that are no longer needed.
- Do not retry after an uncertain live send result; reconcile first through
  provider execution and mailbox evidence.

Remaining before real delivery:

- operator-entered live mailbox acceptance must pass;
- exact sender and recipient allowlists must be configured;
- a separate live adapter implementation and review are required;
- the first live send must be approved as its own single action;
- autonomous campaign workers remain disabled.
