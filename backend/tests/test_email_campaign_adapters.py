"""Tests for read-only external email campaign adapter contracts."""

from datetime import datetime
from uuid import uuid4

import pytest

from app.services.email_campaign_adapters import (
    ExternalCampaignRecord,
    LemlistCampaignAdapter,
)


class FakeLemlistTransport:
    provider_key = "lemlist"

    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def list_campaigns(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[ExternalCampaignRecord]:
        self.calls.append((limit, offset))
        return [
            ExternalCampaignRecord(
                external_id="lem-campaign-1",
                name="Lemlist Welcome",
                status="running",
                audience_count=50,
                sent_count=20,
                reply_count=4,
                bounce_count=1,
                created_at=datetime(2026, 1, 1, 8, 0, 0),
                updated_at=datetime(2026, 1, 2, 8, 0, 0),
            )
        ]


def test_lemlist_adapter_normalizes_fake_transport_records() -> None:
    company_id = uuid4()
    transport = FakeLemlistTransport()
    adapter = LemlistCampaignAdapter(transport)

    items, total = adapter.list_campaigns(
        company_id=company_id,
        limit=25,
        offset=0,
    )

    assert total == 1
    assert transport.calls == [(25, 0)]
    assert items[0].company_id == company_id
    assert items[0].provider_key == "lemlist"
    assert items[0].external_campaign_id == "lem-campaign-1"
    assert items[0].name == "Lemlist Welcome"
    assert items[0].sent_count == 20
    assert items[0].created_at.tzinfo is not None
    assert "secret" not in items[0].model_dump_json().lower()


def test_lemlist_adapter_rejects_wrong_transport_provider() -> None:
    class WrongTransport(FakeLemlistTransport):
        provider_key = "other"

    with pytest.raises(ValueError):
        LemlistCampaignAdapter(WrongTransport())
