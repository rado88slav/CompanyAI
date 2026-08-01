# Troubleshooting CompanyAI Local Edition

## Dashboard Does Not Open

Run:

```bash
scripts/local/status.sh
scripts/local/health-check.sh
```

Confirm Docker Desktop is running and that no other application uses port `8080`.

## Backend Is Not Ready

Readiness depends on PostgreSQL and migrations. Run:

```bash
scripts/local/logs.sh backend migrate
```

Migration errors prevent unsafe startup. The runtime does not recreate or wipe the database automatically.

## Direct Page Refresh Shows an Error

The local Nginx runtime supports SPA fallback for routes such as `/settings`, `/activity`, `/documentation`, `/providers`, `/agent`, `/approvals`, `/campaigns` and `/system-status`. If refresh fails, rebuild and restart:

```bash
scripts/local/restart.sh
```

## Data Persistence

Data is stored in named Docker volumes. Normal stop, start and rebuild commands keep data. Do not remove Docker volumes unless you intend to delete local data.

## Support Bundle

Run:

```bash
scripts/local/diagnose.sh
```

The bundle contains sanitized container status, image metadata, volume metadata and recent logs. It does not contain `.env.local`, passwords, tokens, credential keyrings or provider secrets.

## External Providers

Some provider features require internet access and real credentials. Current
safety boundaries still prevent campaign launches, phone calls and paid
actions.

## SMTP/IMAP Mailbox Test Fails

Generic SMTP/IMAP tests return safe categories:

- `dns_failure`: check the host name and local DNS/network access.
- `connection_failure`: check host, port, firewall and whether the server is reachable.
- `tls_failure`: the server certificate must be valid for the host and trusted by the platform. There is no option to accept invalid certificates.
- `authentication_failure`: check username and mailbox password. Do not paste the password into logs or docs.
- `folder_not_found`: check the configured IMAP folder, usually `INBOX`.
- `timeout`: check network latency, firewall inspection and server responsiveness.

SMTP tests do not send email. IMAP tests open the configured folder read-only
and do not change, move, mark or delete messages. A mailbox remains inactive
until an active encrypted credential exists and both protocol tests succeed.

If mailbox creation succeeds but password storage fails, keep the saved
connection. Open Provider Connections and use **Set password** on the Generic
SMTP/IMAP card. The card shows only safe status text:

- `Password missing`: no active encrypted password credential exists. Test SMTP,
  Test IMAP and Activate stay disabled.
- `Password configured`: an active encrypted password credential exists. SMTP
  and IMAP tests can be run, but the password is never returned or redisplayed.

Use **Replace password** to rotate an existing active password credential. This
uses the Provider Credential API and clears prior SMTP/IMAP acceptance health, so
both protocol tests must succeed again before activation. Use **Edit mailbox
settings** only for non-secret mailbox fields such as host, port, username,
folder and display name; the password is never part of that form.

## Single-Message Test Is Rejected

The controlled one-message test is intentionally strict. Check:

- the selected provider is an active Generic SMTP/IMAP mailbox;
- SMTP and IMAP tests both succeeded after the latest credential/config change;
- the recipient and sender are exact allowlist entries;
- the subject starts with `[COMPANYAI TEST]`;
- the idempotency key has not been used before;
- emergency stop is disabled only for the test window;
- any configured working-hours policy currently allows the action;
- a different authorized administrator approved the exact Approval Manager
  request before simulation execution.

Current execution is simulation only. A rejection does not mean SMTP was
contacted.

## AI Agent Preview Task Is Denied

The Email Operations Preview Agent denies forbidden sends by design. Confirm:

- the agent is active;
- the task is one of the built-in synthetic preview tasks;
- no real recipient list or credential-like input was entered;
- Approval Manager status is reviewed before treating a proposal as actionable.

OpenClaw is not integrated in this runtime. AI Agent results are produced by a
deterministic local preview adapter only.
