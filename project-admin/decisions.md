# Architecture Decisions

## 001 — Development environment
Use Windows 10 with WSL2, Ubuntu and Docker Desktop.

## 002 — Project location
Store the project in the WSL Linux filesystem:

/home/rado/projects/company-ai

Do not develop directly under /mnt/c/.

## 003 — Automation
Prefer repeatable Bash scripts instead of long sequences of manual commands.

## 004 — Platform structure
Build a modular MVP with:
- dashboard
- backend API
- local agent
- database
- integrations
- configuration
- storage
- administration

## 005 — Integration design
External email and phone platforms must be replaceable through configuration and adapters.

## 006 — Company separation
Future support for multiple companies must use isolated company context, credentials and data.
