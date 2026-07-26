# First-Run Setup

CompanyAI must not create a default administrator, default password or reusable bootstrap credential.

## Current Beta Flow

This milestone keeps the existing secure administrator creation workflow and documents the required setup state. A graphical first-run wizard remains planned because it must safely generate secrets, create the first company and close permanently after initialization.

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
3. Use the existing secure administrator creation workflow from the backend container.
4. Sign in through the dashboard.
5. Confirm company membership and active company selection.

The dashboard must show authentication-required or setup-required states rather than implying a default account exists.
