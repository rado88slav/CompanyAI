"""Authenticated company-scoped thin email workflow API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.company_authorization import require_approvals_decide, require_approvals_read, require_emails_read, require_emails_write, require_provider_executions_manage
from app.schemas.company_context import ActiveCompanyContext
from app.schemas.email import EmailApprovalListResponse, InboundEmailDetail, InboundEmailListResponse, InboundEmailSummary, OutboundEmailResponse, ReplyProposalResponse, ReplyProposalWrite, SendReplyRequest, SingleMessageApprovalRequest, SingleMessageApprovalResponse, SingleMessageLiveExecutionRequest, SingleMessageLiveExecutionResponse, SingleMessagePreviewRequest, SingleMessagePreviewResponse, SingleMessageRecipientAllowlistResponse, SingleMessageRecipientAllowlistUpdate, SingleMessageSimulationRequest, SingleMessageSimulationResponse, TestInboundEmailImport
from app.services.email import EmailConflictError, EmailForbiddenError, EmailNotFoundError, EmailWorkflowService, get_email_workflow_service
from app.services.approval_manager import ApprovalConflictError, ApprovalForbiddenError, ApprovalNotFoundError, ApprovalValidationError

router = APIRouter(prefix="/companies/{company_id}", tags=["email-workflow"])

def handle(exc: Exception):
    if isinstance(exc, (EmailNotFoundError, ApprovalNotFoundError)): raise HTTPException(404, "Email workflow resource was not found.") from exc
    if isinstance(exc, (EmailForbiddenError, ApprovalForbiddenError)): raise HTTPException(403, "Email reply action is not authorized.") from exc
    if isinstance(exc, (EmailConflictError, ApprovalConflictError, ApprovalValidationError)): raise HTTPException(409, "Email workflow conflicts with its current state.") from exc
    raise exc


@router.post("/emails/single-message-tests/preview", response_model=SingleMessagePreviewResponse)
def preview_single_message_test(company_id: UUID, data: SingleMessagePreviewRequest, context: Annotated[ActiveCompanyContext, Depends(require_provider_executions_manage)], service: Annotated[EmailWorkflowService, Depends(get_email_workflow_service)]):
    try: return service.preview_single_message(company_id=company_id, data=data, actor=context.administrator)
    except Exception as exc: handle(exc)


@router.post("/emails/single-message-tests/request-approval", response_model=SingleMessageApprovalResponse, status_code=status.HTTP_201_CREATED)
def request_single_message_test_approval(company_id: UUID, data: SingleMessageApprovalRequest, context: Annotated[ActiveCompanyContext, Depends(require_provider_executions_manage)], service: Annotated[EmailWorkflowService, Depends(get_email_workflow_service)]):
    try: return service.request_single_message_approval(company_id=company_id, data=data, actor=context.administrator)
    except Exception as exc: handle(exc)


@router.post("/emails/single-message-tests/execute-simulation", response_model=SingleMessageSimulationResponse)
def execute_single_message_test_simulation(company_id: UUID, data: SingleMessageSimulationRequest, context: Annotated[ActiveCompanyContext, Depends(require_provider_executions_manage)], service: Annotated[EmailWorkflowService, Depends(get_email_workflow_service)]):
    try: return service.execute_single_message_simulation(company_id=company_id, data=data, actor=context.administrator)
    except Exception as exc: handle(exc)


@router.post("/emails/single-message-tests/execute-live", response_model=SingleMessageLiveExecutionResponse)
def execute_single_message_test_live(company_id: UUID, data: SingleMessageLiveExecutionRequest, context: Annotated[ActiveCompanyContext, Depends(require_provider_executions_manage)], service: Annotated[EmailWorkflowService, Depends(get_email_workflow_service)]):
    try: return service.execute_single_message_live(company_id=company_id, data=data, actor=context.administrator)
    except Exception as exc: handle(exc)


@router.get("/emails/single-message-tests/recipient-allowlist", response_model=SingleMessageRecipientAllowlistResponse)
def get_single_message_recipient_allowlist(company_id: UUID, _context: Annotated[ActiveCompanyContext, Depends(require_provider_executions_manage)], service: Annotated[EmailWorkflowService, Depends(get_email_workflow_service)]):
    try: return service.single_message_recipient_allowlist(company_id=company_id)
    except Exception as exc: handle(exc)


@router.post("/emails/single-message-tests/recipient-allowlist", response_model=SingleMessageRecipientAllowlistResponse)
def add_single_message_recipient_allowlist(company_id: UUID, data: SingleMessageRecipientAllowlistUpdate, context: Annotated[ActiveCompanyContext, Depends(require_provider_executions_manage)], service: Annotated[EmailWorkflowService, Depends(get_email_workflow_service)]):
    try: return service.add_single_message_recipient_allowlist(company_id=company_id, data=data, actor=context.administrator)
    except Exception as exc: handle(exc)

@router.post("/emails/test-import", response_model=InboundEmailSummary, status_code=status.HTTP_201_CREATED)
def import_test_email(company_id: UUID, data: TestInboundEmailImport, context: Annotated[ActiveCompanyContext, Depends(require_emails_write)], service: Annotated[EmailWorkflowService, Depends(get_email_workflow_service)]):
    try: return service.summary(service.import_test(company_id, data, context.administrator))
    except Exception as exc: handle(exc)

@router.get("/emails", response_model=InboundEmailListResponse)
def list_emails(company_id: UUID, _context: Annotated[ActiveCompanyContext, Depends(require_emails_read)], service: Annotated[EmailWorkflowService, Depends(get_email_workflow_service)], limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    items, total = service.list(company_id, limit, offset)
    return InboundEmailListResponse(items=items, total=total, limit=limit, offset=offset)

@router.get("/emails/{email_id}", response_model=InboundEmailDetail)
def get_email(company_id: UUID, email_id: UUID, _context: Annotated[ActiveCompanyContext, Depends(require_emails_read)], service: Annotated[EmailWorkflowService, Depends(get_email_workflow_service)]):
    try: return service.detail(company_id, email_id)
    except Exception as exc: handle(exc)

@router.post("/emails/{email_id}/reply-proposals", response_model=ReplyProposalResponse, status_code=201)
def create_proposal(company_id: UUID, email_id: UUID, data: ReplyProposalWrite | None, context: Annotated[ActiveCompanyContext, Depends(require_emails_write)], service: Annotated[EmailWorkflowService, Depends(get_email_workflow_service)]):
    try: return service.create_proposal(company_id, email_id, data, context.administrator)
    except Exception as exc: handle(exc)

@router.patch("/reply-proposals/{proposal_id}", response_model=ReplyProposalResponse)
def update_proposal(company_id: UUID, proposal_id: UUID, data: ReplyProposalWrite, context: Annotated[ActiveCompanyContext, Depends(require_emails_write)], service: Annotated[EmailWorkflowService, Depends(get_email_workflow_service)]):
    try: return service.update_proposal(company_id, proposal_id, data, context.administrator)
    except Exception as exc: handle(exc)

@router.post("/reply-proposals/{proposal_id}/submit", response_model=ReplyProposalResponse)
def submit_proposal(company_id: UUID, proposal_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_emails_write)], service: Annotated[EmailWorkflowService, Depends(get_email_workflow_service)]):
    try: return service.submit(company_id, proposal_id, context.administrator)
    except Exception as exc: handle(exc)

@router.post("/reply-proposals/{proposal_id}/send", response_model=OutboundEmailResponse)
def send_proposal(company_id: UUID, proposal_id: UUID, data: SendReplyRequest, context: Annotated[ActiveCompanyContext, Depends(require_provider_executions_manage)], service: Annotated[EmailWorkflowService, Depends(get_email_workflow_service)]):
    try: return service.send(company_id, proposal_id, data, context.administrator)
    except Exception as exc: handle(exc)

@router.get("/email-approvals", response_model=EmailApprovalListResponse)
def list_email_approvals(company_id: UUID, _context: Annotated[ActiveCompanyContext, Depends(require_approvals_read)], service: Annotated[EmailWorkflowService, Depends(get_email_workflow_service)], limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    items, total = service.list_approvals(company_id, limit, offset)
    return EmailApprovalListResponse(items=items, total=total, limit=limit, offset=offset)

@router.post("/email-approvals/{approval_id}/approve")
def approve_email_reply(company_id: UUID, approval_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_approvals_decide)], service: Annotated[EmailWorkflowService, Depends(get_email_workflow_service)]):
    try:
        role = context.membership.role if context.membership else None
        item = service.decide(company_id, approval_id, context.administrator, role, True)
        return {"id": item.id, "status": item.status}
    except Exception as exc: handle(exc)

@router.post("/email-approvals/{approval_id}/reject")
def reject_email_reply(company_id: UUID, approval_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_approvals_decide)], service: Annotated[EmailWorkflowService, Depends(get_email_workflow_service)]):
    try:
        role = context.membership.role if context.membership else None
        item = service.decide(company_id, approval_id, context.administrator, role, False)
        return {"id": item.id, "status": item.status}
    except Exception as exc: handle(exc)
