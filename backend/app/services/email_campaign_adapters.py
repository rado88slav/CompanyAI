"""Read-only external email campaign adapter contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from app.schemas.email_campaign import EmailCampaignSummary


@dataclass(frozen=True, slots=True)
class ExternalCampaignRecord:
    """Provider-neutral campaign fields returned by adapter transports."""

    external_id: str
    name: str
    status: str
    audience_count: int
    sent_count: int
    reply_count: int
    bounce_count: int
    created_at: datetime
    updated_at: datetime


class EmailCampaignReadTransport(Protocol):
    """Transport boundary for provider-specific read-only campaign listing."""

    provider_key: str

    def list_campaigns(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[ExternalCampaignRecord]:
        """Return provider campaigns without mutating provider state."""


class EmailCampaignReadAdapter(Protocol):
    """Normalize provider campaign records into internal read schemas."""

    provider_key: str

    def list_campaigns(
        self,
        *,
        company_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[EmailCampaignSummary], int]:
        """Return normalized campaign summaries for one company."""


class LemlistCampaignAdapter:
    """Normalize Lemlist campaign reads behind the provider abstraction."""

    provider_key = "lemlist"

    def __init__(self, transport: EmailCampaignReadTransport) -> None:
        if transport.provider_key != self.provider_key:
            raise ValueError("Transport provider key does not match Lemlist.")
        self._transport = transport

    def list_campaigns(
        self,
        *,
        company_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[EmailCampaignSummary], int]:
        records = self._transport.list_campaigns(limit=limit, offset=offset)
        return [
            self._normalize(company_id=company_id, record=record)
            for record in records
        ], len(records)

    def _normalize(
        self,
        *,
        company_id: UUID,
        record: ExternalCampaignRecord,
    ) -> EmailCampaignSummary:
        return EmailCampaignSummary(
            id=uuid5(
                NAMESPACE_URL,
                f"company-ai:{company_id}:lemlist-campaign:{record.external_id}",
            ),
            company_id=company_id,
            provider_key=self.provider_key,
            external_campaign_id=record.external_id,
            name=record.name,
            status=record.status,
            audience_count=max(record.audience_count, 0),
            sent_count=max(record.sent_count, 0),
            reply_count=max(record.reply_count, 0),
            bounce_count=max(record.bounce_count, 0),
            created_at=_aware_datetime(record.created_at),
            updated_at=_aware_datetime(record.updated_at),
        )


def _aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
