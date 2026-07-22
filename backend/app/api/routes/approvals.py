"""Authenticated human approval, policy and usage endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.company_authorization import require_approvals_decide, require_approvals_read, require_approvals_request, require_authorization_policies_manage, require_authorization_policies_read, require_authorization_usage_read
from app.models.company_membership import CompanyRole
from app.schemas.approval import ApprovalDecisionCreate, ApprovalDenialCreate, ApprovalRequestCreate, ApprovalRequestListResponse, ApprovalRequestResponse, ManualPolicyCreate, PolicyListResponse, PolicyResponse, UsageListResponse, UsageResponse
from app.schemas.company_context import ActiveCompanyContext
from app.services.approval_manager import ApprovalConflictError, ApprovalForbiddenError, ApprovalManagerService, ApprovalNotFoundError, ApprovalValidationError, get_approval_manager_service

router = APIRouter(prefix="/companies/{company_id}", tags=["approvals"])

def _error(exc: Exception) -> None:
    if isinstance(exc, ApprovalNotFoundError): raise HTTPException(404, "Approval resource was not found.") from exc
    if isinstance(exc, ApprovalForbiddenError): raise HTTPException(403, "Approval operation is not permitted.") from exc
    if isinstance(exc, ApprovalConflictError): raise HTTPException(409, "Approval resource is no longer in the required state.") from exc
    if isinstance(exc, ApprovalValidationError): raise HTTPException(422, "Approved authorization must not broaden the request.") from exc
    raise exc

def _role(context: ActiveCompanyContext) -> str | None: return context.membership.role if context.membership else None
def _operator(context: ActiveCompanyContext) -> bool: return not context.is_platform_superuser and _role(context) == CompanyRole.OPERATOR.value

@router.post("/approval-requests", response_model=ApprovalRequestResponse, status_code=status.HTTP_201_CREATED)
def create_request(company_id: UUID, payload: ApprovalRequestCreate, context: Annotated[ActiveCompanyContext, Depends(require_approvals_request)], service: Annotated[ApprovalManagerService, Depends(get_approval_manager_service)]):
    return service.create_request(company_id=company_id, actor=context.administrator, payload=payload)

@router.get("/approval-requests", response_model=ApprovalRequestListResponse)
def list_requests(company_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_approvals_read)], service: Annotated[ApprovalManagerService, Depends(get_approval_manager_service)], status_filter: str | None = Query(None, alias="status"), action_type: str | None = None, tool_identifier: str | None = None, risk_level: str | None = None, campaign_id: UUID | None = None, requester_administrator_id: UUID | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    if _operator(context): requester_administrator_id = context.administrator.id
    items, total = service.list_requests(company_id=company_id, actor=context.administrator, own_only=_operator(context), requester_administrator_id=requester_administrator_id, status=status_filter, action_type=action_type, tool_identifier=tool_identifier, risk_level=risk_level, campaign_id=campaign_id, limit=limit, offset=offset)
    return ApprovalRequestListResponse(items=items, total=total, limit=limit, offset=offset)

@router.get("/approval-requests/{request_id}", response_model=ApprovalRequestResponse)
def get_request(company_id: UUID, request_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_approvals_read)], service: Annotated[ApprovalManagerService, Depends(get_approval_manager_service)]):
    try: return service.get_request(company_id=company_id, request_id=request_id, actor=context.administrator, own_only=_operator(context))
    except Exception as exc: _error(exc)

@router.post("/approval-requests/{request_id}/approve", response_model=ApprovalRequestResponse)
def approve(company_id: UUID, request_id: UUID, payload: ApprovalDecisionCreate, context: Annotated[ActiveCompanyContext, Depends(require_approvals_decide)], service: Annotated[ApprovalManagerService, Depends(get_approval_manager_service)]):
    try: return service.approve(company_id=company_id, request_id=request_id, actor=context.administrator, actor_role=_role(context), payload=payload)
    except Exception as exc: _error(exc)

@router.post("/approval-requests/{request_id}/deny", response_model=ApprovalRequestResponse)
def deny(company_id: UUID, request_id: UUID, payload: ApprovalDenialCreate, context: Annotated[ActiveCompanyContext, Depends(require_approvals_decide)], service: Annotated[ApprovalManagerService, Depends(get_approval_manager_service)]):
    try: return service.deny(company_id=company_id, request_id=request_id, actor=context.administrator, actor_role=_role(context), reason=payload.reason)
    except Exception as exc: _error(exc)

@router.post("/approval-requests/{request_id}/cancel", response_model=ApprovalRequestResponse)
def cancel(company_id: UUID, request_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_approvals_request)], service: Annotated[ApprovalManagerService, Depends(get_approval_manager_service)]):
    try: return service.cancel(company_id=company_id, request_id=request_id, actor=context.administrator, may_cancel_any=context.is_platform_superuser or _role(context) in {CompanyRole.OWNER.value, CompanyRole.ADMIN.value})
    except Exception as exc: _error(exc)

@router.get("/authorization-policies", response_model=PolicyListResponse)
def list_policies(company_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_authorization_policies_read)], service: Annotated[ApprovalManagerService, Depends(get_approval_manager_service)], status_filter: str | None = Query(None, alias="status"), effect: str | None = None, action_type: str | None = None, tool_identifier: str | None = None, campaign_id: UUID | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    items, total = service.list_policies(company_id=company_id, status=status_filter, effect=effect, action_type=action_type, tool_identifier=tool_identifier, campaign_id=campaign_id, limit=limit, offset=offset)
    return PolicyListResponse(items=items, total=total, limit=limit, offset=offset)

@router.post("/authorization-policies", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
def create_policy(company_id: UUID, payload: ManualPolicyCreate, context: Annotated[ActiveCompanyContext, Depends(require_authorization_policies_manage)], service: Annotated[ApprovalManagerService, Depends(get_approval_manager_service)]):
    try: return service.create_manual_policy(company_id=company_id, actor=context.administrator, actor_role=_role(context), payload=payload)
    except Exception as exc: _error(exc)

@router.get("/authorization-policies/{policy_id}", response_model=PolicyResponse)
def get_policy(company_id: UUID, policy_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_authorization_policies_read)], service: Annotated[ApprovalManagerService, Depends(get_approval_manager_service)]):
    try: return service.get_policy(company_id=company_id, policy_id=policy_id)
    except Exception as exc: _error(exc)

@router.post("/authorization-policies/{policy_id}/revoke", response_model=PolicyResponse)
def revoke_policy(company_id: UUID, policy_id: UUID, payload: ApprovalDenialCreate, context: Annotated[ActiveCompanyContext, Depends(require_authorization_policies_manage)], service: Annotated[ApprovalManagerService, Depends(get_approval_manager_service)]):
    try: return service.revoke_policy(company_id=company_id, policy_id=policy_id, actor=context.administrator, reason=payload.reason)
    except Exception as exc: _error(exc)

@router.get("/authorization-usages", response_model=UsageListResponse)
def list_usages(company_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_authorization_usage_read)], service: Annotated[ApprovalManagerService, Depends(get_approval_manager_service)], status_filter: str | None = Query(None, alias="status"), action_type: str | None = None, campaign_id: UUID | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    items, total = service.list_usages(company_id=company_id, status=status_filter, action_type=action_type, campaign_id=campaign_id, limit=limit, offset=offset)
    return UsageListResponse(items=items, total=total, limit=limit, offset=offset)

@router.get("/authorization-usages/{usage_id}", response_model=UsageResponse)
def get_usage(company_id: UUID, usage_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_authorization_usage_read)], service: Annotated[ApprovalManagerService, Depends(get_approval_manager_service)]):
    try: return service.get_usage(company_id=company_id, usage_id=usage_id)
    except Exception as exc: _error(exc)
