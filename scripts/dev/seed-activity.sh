#!/usr/bin/env bash
# Description: Seed deterministic development-only Activity Center events.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPANY_SLUG="${1:-company-test}"

cd "$ROOT_DIR"

docker compose exec -T backend python - "$COMPANY_SLUG" <<'PY'
import os
import sys
from uuid import UUID, uuid5

from app.db.session import SessionFactory
from app.models.audit_log import AuditLog
from app.models.company import Company
from sqlalchemy import select

NAMESPACE = UUID("ba32effb-96ce-4b0b-97ef-e1ed7df50a51")
SEEDS = (
    ("agent-execution-completed", "agent_tool.invoked", "agent", {"tool_key": "dashboard.summary.read", "status": "succeeded", "development_only": True}),
    ("approval-requested", "approval_request.created", "approval_request", {"risk_level": "medium", "requires_approval": True, "development_only": True}),
    ("approval-granted", "approval_request.approved", "approval_request", {"status": "approved", "development_only": True}),
    ("provider-connection-healthy", "provider_connection.activated", "provider_connection", {"provider_key": "local_test_email", "status": "healthy", "development_only": True}),
    ("email-campaign-imported", "email.imported", "inbound_email", {"provider_key": "local_mock_email", "status": "read_only", "development_only": True}),
    ("system-health-check", "company.updated", "company", {"operation": "development_health_check", "status": "ok", "development_only": True}),
    ("user-login", "administrator.authenticated", "administrator", {"operation": "development_login_sample", "status": "succeeded", "development_only": True}),
)

company_slug = sys.argv[1]
environment = os.getenv("APP_ENV", "development")
if environment != "development":
    raise SystemExit("Refusing to seed activity outside APP_ENV=development.")

with SessionFactory() as session:
    company = session.scalar(select(Company).where(Company.slug == company_slug))
    if company is None:
        raise SystemExit(f"Development company not found: {company_slug}")
    inserted = 0
    skipped = 0
    for key, action, resource_type, details in SEEDS:
        event_id = uuid5(NAMESPACE, f"{company.id}:{key}")
        if session.get(AuditLog, event_id) is not None:
            skipped += 1
            continue
        session.add(AuditLog(
            id=event_id,
            scope="company",
            company_id=company.id,
            actor_type="system",
            actor_administrator_id=None,
            actor_agent_id=None,
            action=action,
            resource_type=resource_type,
            resource_id=company.id,
            details={"seed_key": key, **details},
        ))
        inserted += 1
    session.commit()

print(f"Development activity seed complete: inserted={inserted} skipped={skipped} company_slug={company_slug}")
PY
