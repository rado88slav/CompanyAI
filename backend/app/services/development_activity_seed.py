"""Development-only deterministic activity seed data."""

from dataclasses import dataclass
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditActorType, AuditLog, AuditScope
from app.models.company import Company

DEVELOPMENT_ACTIVITY_NAMESPACE = UUID("ba32effb-96ce-4b0b-97ef-e1ed7df50a51")


@dataclass(frozen=True, slots=True)
class DevelopmentActivitySeed:
    """One deterministic development activity event."""

    key: str
    action: str
    resource_type: str
    details: dict[str, str | bool]

    def event_id(self, company_id: UUID) -> UUID:
        return uuid5(DEVELOPMENT_ACTIVITY_NAMESPACE, f"{company_id}:{self.key}")


DEVELOPMENT_ACTIVITY_SEEDS = (
    DevelopmentActivitySeed(
        key="agent-execution-completed",
        action="agent_tool.invoked",
        resource_type="agent",
        details={"tool_key": "dashboard.summary.read", "status": "succeeded", "development_only": True},
    ),
    DevelopmentActivitySeed(
        key="approval-requested",
        action="approval_request.created",
        resource_type="approval_request",
        details={"risk_level": "medium", "requires_approval": True, "development_only": True},
    ),
    DevelopmentActivitySeed(
        key="approval-granted",
        action="approval_request.approved",
        resource_type="approval_request",
        details={"status": "approved", "development_only": True},
    ),
    DevelopmentActivitySeed(
        key="provider-connection-healthy",
        action="provider_connection.activated",
        resource_type="provider_connection",
        details={"provider_key": "local_test_email", "status": "healthy", "development_only": True},
    ),
    DevelopmentActivitySeed(
        key="email-campaign-imported",
        action="email.imported",
        resource_type="inbound_email",
        details={"provider_key": "local_mock_email", "status": "read_only", "development_only": True},
    ),
    DevelopmentActivitySeed(
        key="system-health-check",
        action="company.updated",
        resource_type="company",
        details={"operation": "development_health_check", "status": "ok", "development_only": True},
    ),
    DevelopmentActivitySeed(
        key="user-login",
        action="administrator.authenticated",
        resource_type="administrator",
        details={"operation": "development_login_sample", "status": "succeeded", "development_only": True},
    ),
)


def get_development_company(session: Session, *, slug: str) -> Company:
    """Return the target development company by slug."""

    company = session.scalar(select(Company).where(Company.slug == slug))
    if company is None:
        raise ValueError(f"Development company not found: {slug}")
    return company


def seed_development_activity(
    session: Session,
    *,
    company_slug: str = "company-test",
) -> tuple[int, int]:
    """Insert deterministic company-scoped activity events if absent."""

    company = get_development_company(session, slug=company_slug)
    inserted = 0
    skipped = 0
    for seed in DEVELOPMENT_ACTIVITY_SEEDS:
        event_id = seed.event_id(company.id)
        if session.get(AuditLog, event_id) is not None:
            skipped += 1
            continue
        session.add(
            AuditLog(
                id=event_id,
                scope=AuditScope.COMPANY.value,
                company_id=company.id,
                actor_type=AuditActorType.SYSTEM.value,
                actor_administrator_id=None,
                actor_agent_id=None,
                action=seed.action,
                resource_type=seed.resource_type,
                resource_id=company.id,
                details={"seed_key": seed.key, **seed.details},
            )
        )
        inserted += 1
    session.commit()
    return inserted, skipped
