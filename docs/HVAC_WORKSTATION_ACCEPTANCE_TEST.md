# HVAC Workstation Acceptance Test

This checklist must be completed on the real workstation before using CompanyAI for a 20-50 prospect pilot.

## Installation

- Install from offline package copied to internal SSD.
- Import Docker images without registry pulls.
- Generate local secrets.
- Start at `http://localhost:8080`.
- Confirm no Vite development server is used.
- Confirm backend and database ports are not exposed.
- Restart Windows and confirm the app starts correctly.

## Operations

- Login and logout.
- Select active company.
- Confirm Settings persistence.
- Review Activity Center and Audit Log.
- Verify provider status.
- Test graceful internet loss.
- Test Docker Desktop restart.

## Backup and Restore

- Create deterministic business test record.
- Back up to external disk.
- Alter the deterministic record.
- Restore backup.
- Verify record, login, configuration and health.

## Email Sandbox

- Send one approved test message to an allowlisted team address.
- Reject a non-allowlisted address.
- Reject sending without approval.
- Reject duplicate send.
- Enforce hourly and daily quotas.
- Enable emergency stop and verify sends are rejected.
- Verify all events appear in Activity and Audit.
- Confirm no secrets appear in logs or support bundle.

Do not use real HVAC prospects until this checklist passes.
