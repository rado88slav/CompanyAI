"""Pydantic schemas for append-only audit events."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.models.audit_log import AuditActorType, AuditScope


class AuditLogResponse(BaseModel):
    """Public audit event representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scope: AuditScope
    company_id: UUID | None
    actor_type: AuditActorType
    actor_administrator_id: UUID | None
    action: str
    resource_type: str
    resource_id: UUID | None
    details: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Paginated company audit activity."""

    items: list[AuditLogResponse]
    total: int
    limit: int
    offset: int
