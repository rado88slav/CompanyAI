"""Company-scoped email campaign and automation schedule APIs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.company_authorization import require_emails_read, require_emails_write
from app.schemas.company_context import ActiveCompanyContext
from app.schemas.email_campaign import CampaignSchedulePauseRequest, CampaignSchedulePreviewRequest, CampaignSchedulePreviewResponse, CampaignScheduleSettings, EmailAutomationWorkerSimulationRequest, EmailAutomationWorkerSimulationResponse, EmailCampaignListResponse
from app.services.email_automation import EmailAutomationService, EmailAutomationValidationError, get_email_automation_service
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


def _handle_automation_error(exc: Exception) -> None:
    if isinstance(exc, EmailAutomationValidationError):
        raise HTTPException(409, "Email automation schedule conflicts with current company resources.") from exc
    raise exc


@router.get("/email-automation/schedule", response_model=CampaignScheduleSettings)
def get_email_automation_schedule(
    company_id: UUID,
    _context: Annotated[ActiveCompanyContext, Depends(require_emails_read)],
    service: Annotated[EmailAutomationService, Depends(get_email_automation_service)],
) -> CampaignScheduleSettings:
    try:
        return service.get_settings(company_id=company_id)
    except Exception as exc:
        _handle_automation_error(exc)


@router.put("/email-automation/schedule", response_model=CampaignScheduleSettings)
def save_email_automation_schedule(
    company_id: UUID,
    data: CampaignScheduleSettings,
    context: Annotated[ActiveCompanyContext, Depends(require_emails_write)],
    service: Annotated[EmailAutomationService, Depends(get_email_automation_service)],
) -> CampaignScheduleSettings:
    try:
        return service.save_settings(company_id=company_id, data=data, actor=context.administrator)
    except Exception as exc:
        _handle_automation_error(exc)


@router.post("/email-automation/schedule/preview", response_model=CampaignSchedulePreviewResponse)
def preview_email_automation_schedule(
    company_id: UUID,
    data: CampaignSchedulePreviewRequest,
    context: Annotated[ActiveCompanyContext, Depends(require_emails_write)],
    service: Annotated[EmailAutomationService, Depends(get_email_automation_service)],
) -> CampaignSchedulePreviewResponse:
    try:
        return service.preview(company_id=company_id, request=data, actor=context.administrator)
    except Exception as exc:
        _handle_automation_error(exc)


@router.post("/email-automation/schedule/pause", response_model=CampaignScheduleSettings)
def pause_email_automation_schedule(
    company_id: UUID,
    data: CampaignSchedulePauseRequest,
    context: Annotated[ActiveCompanyContext, Depends(require_emails_write)],
    service: Annotated[EmailAutomationService, Depends(get_email_automation_service)],
) -> CampaignScheduleSettings:
    try:
        return service.pause(company_id=company_id, reason=data.reason, actor=context.administrator)
    except Exception as exc:
        _handle_automation_error(exc)


@router.post("/email-automation/schedule/resume", response_model=CampaignScheduleSettings)
def resume_email_automation_schedule(
    company_id: UUID,
    context: Annotated[ActiveCompanyContext, Depends(require_emails_write)],
    service: Annotated[EmailAutomationService, Depends(get_email_automation_service)],
) -> CampaignScheduleSettings:
    try:
        return service.resume(company_id=company_id, actor=context.administrator)
    except Exception as exc:
        _handle_automation_error(exc)


@router.post("/email-automation/worker/simulate", response_model=EmailAutomationWorkerSimulationResponse)
def simulate_email_automation_worker(
    company_id: UUID,
    data: EmailAutomationWorkerSimulationRequest,
    context: Annotated[ActiveCompanyContext, Depends(require_emails_write)],
    service: Annotated[EmailAutomationService, Depends(get_email_automation_service)],
) -> EmailAutomationWorkerSimulationResponse:
    try:
        return service.simulate_worker(company_id=company_id, request=data, actor=context.administrator)
    except Exception as exc:
        _handle_automation_error(exc)
