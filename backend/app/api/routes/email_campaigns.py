"""Company-scoped read-only mock email campaign APIs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.company_authorization import require_emails_read
from app.schemas.company_context import ActiveCompanyContext
from app.schemas.email_campaign import EmailCampaignListResponse
from app.services.email_campaign import MockEmailCampaignService, get_mock_email_campaign_service

router = APIRouter(prefix="/companies/{company_id}", tags=["email-campaigns"])


@router.get("/email-campaigns", response_model=EmailCampaignListResponse)
def list_email_campaigns(
    company_id: UUID,
    _context: Annotated[ActiveCompanyContext, Depends(require_emails_read)],
    service: Annotated[MockEmailCampaignService, Depends(get_mock_email_campaign_service)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> EmailCampaignListResponse:
    items, total = service.list_campaigns(
        company_id=company_id,
        limit=limit,
        offset=offset,
    )
    return EmailCampaignListResponse(items=items, total=total, limit=limit, offset=offset)
