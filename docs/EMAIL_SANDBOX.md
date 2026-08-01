# Email Sandbox

Email Sandbox is a backend-enforced safety boundary for early real-world testing.

## Default Posture

For local-production runtime, missing sandbox policy fails closed:

- sandbox enabled;
- empty recipient allowlist;
- empty sender allowlist;
- one recipient per message;
- five messages per hour;
- ten messages per day;
- `[COMPANYAI TEST]` subject prefix required;
- approvals required;
- emergency stop supported;
- follow-ups, bulk sends and attachments disabled.

Development mode keeps the existing local-test dry-run workflow available for automated tests and non-production validation.

## Enforcement

The backend send path checks company scope, approval state, provider connection, exact recipient allowlist, sender allowlist, quotas, subject prefix, duplicate-send protection and emergency stop before provider execution.

Rejected attempts are audited with sanitized reason codes. Provider credentials are never exposed to frontend state, logs or diagnostics.

## Single-Message Test

Email Operations now includes a controlled one-message test panel. It requires
one active Generic SMTP/IMAP mailbox whose SMTP and IMAP acceptance checks have
succeeded, one explicit recipient, a unique idempotency key, the
`[COMPANYAI TEST]` subject prefix and an Approval Manager request.

Simulation creates or consumes Provider Execution and Approval Manager records
in dry-run mode and does not open SMTP, decrypt mailbox credentials, send
email, retry uncertain results, use CC/BCC, attach files, enable tracking,
schedule follow-ups or accept recipient lists. The separate LIVE TEST path can
send exactly one plain-text SMTP message only after exact allowlist matching,
Approval Manager authorization and final typed confirmation.

Operator procedure: `docs/SINGLE_MESSAGE_TEST.md`.

## Pilot Boundary

Do not use real HVAC prospects during sandbox acceptance. Initial sends must go only to team-controlled allowlisted addresses.
