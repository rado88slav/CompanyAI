"""Deterministic mock email campaign read model."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import Depends

from app.db.session import get_db_session
from app.schemas.email_campaign import EmailCampaignSummary


class MockEmailCampaignService:
    """Return normalized campaign data without external provider calls."""

    def list_campaigns(
        self,
        *,
        company_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[EmailCampaignSummary], int]:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        fixtures = [
            EmailCampaignSummary(
                id=uuid5(NAMESPACE_URL, f"company-ai:{company_id}:mock-email-campaign:welcome"),
                company_id=company_id,
                provider_key="local_mock_email",
                external_campaign_id="mock-welcome",
                name="Welcome sequence",
                status="draft",
                audience_count=42,
                sent_count=0,
                reply_count=0,
                bounce_count=0,
                created_at=now - timedelta(days=10),
                updated_at=now - timedelta(days=2),
            ),
            EmailCampaignSummary(
                id=uuid5(NAMESPACE_URL, f"company-ai:{company_id}:mock-email-campaign:reengage"),
                company_id=company_id,
                provider_key="local_mock_email",
                external_campaign_id="mock-reengage",
                name="Re-engagement check-in",
                status="paused",
                audience_count=128,
                sent_count=96,
                reply_count=11,
                bounce_count=2,
                created_at=now - timedelta(days=28),
                updated_at=now - timedelta(days=1),
            ),
        ]
        return fixtures[offset : offset + limit], len(fixtures)


def get_mock_email_campaign_service(
    _session: Annotated[object, Depends(get_db_session)],
) -> MockEmailCampaignService:
    return MockEmailCampaignService()
