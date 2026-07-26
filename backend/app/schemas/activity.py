"""Normalized read-only company activity schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ActivityEventResponse(BaseModel):
    """Safe normalized event for operational timelines."""

    id: UUID
    company_id: UUID
    occurred_at: datetime
    category: str
    source: str
    action: str
    title: str
    summary: str
    status: str
    severity: str
    actor_display: str
    entity_type: str
    entity_id: UUID | None
    safe_details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    correlation_id: str | None = None


class ActivityEventListResponse(BaseModel):
    """Paginated normalized company activity."""

    items: list[ActivityEventResponse]
    total: int
    limit: int
    offset: int
