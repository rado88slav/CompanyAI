"""Normalized read-only email campaign schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EmailCampaignSummary(BaseModel):
    id: UUID
    company_id: UUID
    provider_key: str
    external_campaign_id: str
    name: str
    status: str
    audience_count: int
    sent_count: int
    reply_count: int
    bounce_count: int
    created_at: datetime
    updated_at: datetime


class EmailCampaignListResponse(BaseModel):
    items: list[EmailCampaignSummary]
    total: int
    limit: int
    offset: int
