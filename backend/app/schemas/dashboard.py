"""Safe read-only dashboard summary schemas."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from app.models.audit_log import AuditActorType


class DashboardServiceStatus(StrEnum):
    """Public backend service states."""

    OK = "ok"


class DashboardReadinessStatus(StrEnum):
    """Public database readiness states."""

    REACHABLE = "reachable"


class DashboardServiceSummary(BaseModel):
    """Non-secret runtime metadata for the dashboard."""

    status: DashboardServiceStatus
    readiness: DashboardReadinessStatus
    environment: str
    version: str


class DashboardCounts(BaseModel):
    """Company-scoped operational counts."""

    provider_connections: int
    enabled_provider_connections: int
    provider_credentials: int
    pending_approvals: int
    provider_executions: int
    failed_provider_executions: int
    audit_events: int


class DashboardAuditEvent(BaseModel):
    """Explicit safe subset of a recent audit event."""

    id: UUID
    actor_type: AuditActorType
    action: str
    resource_type: str
    resource_id: UUID | None
    created_at: datetime


class DashboardSummaryResponse(BaseModel):
    """Complete read-only overview response."""

    service: DashboardServiceSummary
    counts: DashboardCounts
    recent_audit_events: list[DashboardAuditEvent]
