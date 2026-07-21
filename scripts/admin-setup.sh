#!/usr/bin/env bash
# Description: Create the project administration and documentation files.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADMIN_DIR="$PROJECT_ROOT/project-admin"

echo "======================================"
echo " Company AI - Admin Setup"
echo "======================================"

mkdir -p "$ADMIN_DIR"

cat > "$ADMIN_DIR/progress.md" << 'EOF'
# Project Progress

## Completed
- Windows 10 22H2 verified
- WSL2 installed and configured
- Ubuntu installed
- Docker Desktop integrated with WSL
- Docker Engine tested successfully
- Initial project structure created
- Bash command registry created

## Current Phase
Project foundation and administration setup.

## Last Updated
Update this file after major project changes.
EOF

cat > "$ADMIN_DIR/todo.md" << 'EOF'
# Project To-Do

## Current
- Create project administration files
- Create automatic inventory script
- Initialize Git repository
- Define MVP service architecture
- Create Docker Compose foundation

## Later
- Backend API
- Local AI agent
- Dashboard
- Email platform integrations
- Phone platform integrations
- Task and activity logging
EOF

cat > "$ADMIN_DIR/decisions.md" << 'EOF'
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
EOF

cat > "$ADMIN_DIR/inventory.md" << 'EOF'
# Project Inventory

This file will be generated automatically.

Run:

./scripts/update-inventory.sh
EOF

cat > "$ADMIN_DIR/scripts-index.txt" << 'EOF'
=========================================
Company AI - Scripts Index
=========================================

1. Project setup
scripts/setup.sh

2. Administration setup
scripts/admin-setup.sh
EOF

echo
echo "Administrative files created successfully:"
echo "- project-admin/progress.md"
echo "- project-admin/todo.md"
echo "- project-admin/decisions.md"
echo "- project-admin/inventory.md"
echo "- project-admin/scripts-index.txt"
