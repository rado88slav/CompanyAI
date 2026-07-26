# First-Run Setup

CompanyAI must not create a default administrator, default password or reusable bootstrap credential.

## Current Beta Flow

This milestone adds a safe setup detection endpoint and a single-use local CLI bootstrap. A graphical first-run wizard remains planned because it must safely generate secrets, create the first company and close permanently after initialization.

## Required Security Properties

- Setup is available only while no administrator exists.
- Setup cannot reopen after the first administrator exists.
- Password policy is enforced by the backend.
- Initialization is transactional where practical.
- Concurrent attempts cannot create duplicate first administrators.
- Passwords, hashes and generated secrets are never returned after setup.
- Setup attempts are audited without sensitive values.

## Workstation Procedure

1. Generate `.env.local` secrets locally.
2. Start the Local Edition runtime.
3. Run `python -m app.cli.bootstrap_first_run` inside the backend container.
4. Provide company name, company slug, administrator email, administrator full name, strong password, language and timezone through standard input.
5. Sign in through the dashboard.
6. Confirm company membership and active company selection.

The dashboard must show authentication-required or setup-required states rather than implying a default account exists.

The setup status endpoint is read-only:

```text
GET /api/v1/first-run/status
```

It returns counts and bootstrap method only. It never returns passwords, hashes, tokens or generated secrets.
