"""Company-scoped administrator APIs for agent identity management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.company_authorization import require_agents_manage, require_agents_read
from app.models.agent import AgentStatus, AgentType
from app.schemas.agent import AgentCreate, AgentCredentialCreate, AgentCredentialOneTimeResponse, AgentCredentialResponse, AgentListResponse, AgentPermissionCreate, AgentPermissionResponse, AgentReason, AgentResponse, AgentUpdate
from app.schemas.company_context import ActiveCompanyContext
from app.services.agent_identity import AgentAuthorizationError, AgentConflictError, AgentCredentialNotFoundError, AgentIdentityService, AgentLifecycleError, AgentNotFoundError, AgentPermissionNotFoundError, get_agent_identity_service

router = APIRouter(tags=["agents"])


def _error(exc: Exception) -> None:
    if isinstance(exc, (AgentNotFoundError, AgentCredentialNotFoundError, AgentPermissionNotFoundError)): raise HTTPException(404, "Agent resource was not found.") from exc
    if isinstance(exc, AgentAuthorizationError): raise HTTPException(403, "Insufficient company permission.") from exc
    if isinstance(exc, (AgentConflictError, AgentLifecycleError)): raise HTTPException(409, "Agent operation conflicts with current state.") from exc
    raise exc


@router.post("/companies/{company_id}/agents", response_model=AgentResponse, status_code=201)
def create_agent(company_id: UUID, data: AgentCreate, context: Annotated[ActiveCompanyContext, Depends(require_agents_manage)], service: Annotated[AgentIdentityService, Depends(get_agent_identity_service)]) -> AgentResponse:
    try: item = service.create_agent(company_id=company_id, data=data, actor=context.administrator, membership=context.membership)
    except (AgentConflictError, AgentAuthorizationError) as exc: _error(exc)
    return AgentResponse.model_validate(item)


@router.get("/companies/{company_id}/agents", response_model=AgentListResponse)
def list_agents(company_id: UUID, _context: Annotated[ActiveCompanyContext, Depends(require_agents_read)], service: Annotated[AgentIdentityService, Depends(get_agent_identity_service)], agent_status: AgentStatus | None = Query(default=None, alias="status"), agent_type: AgentType | None = None, search: str | None = Query(default=None, min_length=1, max_length=100), limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)) -> AgentListResponse:
    items, total = service.list_agents(company_id=company_id, status=agent_status.value if agent_status else None, agent_type=agent_type.value if agent_type else None, search=search, limit=limit, offset=offset)
    return AgentListResponse(items=[AgentResponse.model_validate(i) for i in items], total=total, limit=limit, offset=offset)


@router.get("/companies/{company_id}/agents/{agent_id}", response_model=AgentResponse)
def get_agent(company_id: UUID, agent_id: UUID, _context: Annotated[ActiveCompanyContext, Depends(require_agents_read)], service: Annotated[AgentIdentityService, Depends(get_agent_identity_service)]) -> AgentResponse:
    try: return AgentResponse.model_validate(service.get_agent(company_id=company_id, agent_id=agent_id))
    except AgentNotFoundError as exc: _error(exc)


@router.patch("/companies/{company_id}/agents/{agent_id}", response_model=AgentResponse)
def update_agent(company_id: UUID, agent_id: UUID, data: AgentUpdate, context: Annotated[ActiveCompanyContext, Depends(require_agents_manage)], service: Annotated[AgentIdentityService, Depends(get_agent_identity_service)]) -> AgentResponse:
    try: item = service.update_agent(company_id=company_id, agent_id=agent_id, data=data, actor=context.administrator, membership=context.membership)
    except (AgentNotFoundError, AgentAuthorizationError) as exc: _error(exc)
    return AgentResponse.model_validate(item)


def _set_active(company_id: UUID, agent_id: UUID, active: bool, context: ActiveCompanyContext, service: AgentIdentityService) -> AgentResponse:
    try: item = service.set_active(company_id=company_id, agent_id=agent_id, active=active, actor=context.administrator, membership=context.membership)
    except (AgentNotFoundError, AgentAuthorizationError, AgentLifecycleError) as exc: _error(exc)
    return AgentResponse.model_validate(item)


@router.post("/companies/{company_id}/agents/{agent_id}/activate", response_model=AgentResponse)
def activate_agent(company_id: UUID, agent_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_agents_manage)], service: Annotated[AgentIdentityService, Depends(get_agent_identity_service)]) -> AgentResponse: return _set_active(company_id, agent_id, True, context, service)


@router.post("/companies/{company_id}/agents/{agent_id}/deactivate", response_model=AgentResponse)
def deactivate_agent(company_id: UUID, agent_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_agents_manage)], service: Annotated[AgentIdentityService, Depends(get_agent_identity_service)]) -> AgentResponse: return _set_active(company_id, agent_id, False, context, service)


@router.post("/companies/{company_id}/agents/{agent_id}/revoke", response_model=AgentResponse)
def revoke_agent(company_id: UUID, agent_id: UUID, data: AgentReason, context: Annotated[ActiveCompanyContext, Depends(require_agents_manage)], service: Annotated[AgentIdentityService, Depends(get_agent_identity_service)]) -> AgentResponse:
    try: item = service.revoke_agent(company_id=company_id, agent_id=agent_id, reason=data.reason, actor=context.administrator, membership=context.membership)
    except (AgentNotFoundError, AgentAuthorizationError, AgentLifecycleError) as exc: _error(exc)
    return AgentResponse.model_validate(item)


@router.get("/companies/{company_id}/agents/{agent_id}/credentials", response_model=list[AgentCredentialResponse])
def list_credentials(company_id: UUID, agent_id: UUID, _context: Annotated[ActiveCompanyContext, Depends(require_agents_read)], service: Annotated[AgentIdentityService, Depends(get_agent_identity_service)]) -> list[AgentCredentialResponse]:
    try: return [AgentCredentialResponse.model_validate(i) for i in service.list_credentials(company_id=company_id, agent_id=agent_id)]
    except AgentNotFoundError as exc: _error(exc)


@router.post("/companies/{company_id}/agents/{agent_id}/credentials", response_model=AgentCredentialOneTimeResponse, status_code=201)
def create_credential(company_id: UUID, agent_id: UUID, data: AgentCredentialCreate, context: Annotated[ActiveCompanyContext, Depends(require_agents_manage)], service: Annotated[AgentIdentityService, Depends(get_agent_identity_service)]) -> AgentCredentialOneTimeResponse:
    try: result = service.create_credential(company_id=company_id, agent_id=agent_id, name=data.name, expires_at=data.expires_at, actor=context.administrator, membership=context.membership)
    except (AgentNotFoundError, AgentAuthorizationError, AgentLifecycleError) as exc: _error(exc)
    return AgentCredentialOneTimeResponse(**AgentCredentialResponse.model_validate(result.metadata).model_dump(), credential=result.plaintext)


@router.post("/companies/{company_id}/agents/{agent_id}/credentials/{credential_id}/rotate", response_model=AgentCredentialOneTimeResponse)
def rotate_credential(company_id: UUID, agent_id: UUID, credential_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_agents_manage)], service: Annotated[AgentIdentityService, Depends(get_agent_identity_service)]) -> AgentCredentialOneTimeResponse:
    try: result = service.rotate_credential(company_id=company_id, agent_id=agent_id, credential_id=credential_id, actor=context.administrator, membership=context.membership)
    except (AgentNotFoundError, AgentCredentialNotFoundError, AgentAuthorizationError, AgentLifecycleError) as exc: _error(exc)
    return AgentCredentialOneTimeResponse(**AgentCredentialResponse.model_validate(result.metadata).model_dump(), credential=result.plaintext)


@router.post("/companies/{company_id}/agents/{agent_id}/credentials/{credential_id}/revoke", response_model=AgentCredentialResponse)
def revoke_credential(company_id: UUID, agent_id: UUID, credential_id: UUID, data: AgentReason, context: Annotated[ActiveCompanyContext, Depends(require_agents_manage)], service: Annotated[AgentIdentityService, Depends(get_agent_identity_service)]) -> AgentCredentialResponse:
    try: item = service.revoke_credential(company_id=company_id, agent_id=agent_id, credential_id=credential_id, reason=data.reason, actor=context.administrator, membership=context.membership)
    except (AgentNotFoundError, AgentCredentialNotFoundError, AgentAuthorizationError, AgentLifecycleError) as exc: _error(exc)
    return AgentCredentialResponse.model_validate(item)


@router.get("/companies/{company_id}/agents/{agent_id}/permissions", response_model=list[AgentPermissionResponse])
def list_permissions(company_id: UUID, agent_id: UUID, _context: Annotated[ActiveCompanyContext, Depends(require_agents_read)], service: Annotated[AgentIdentityService, Depends(get_agent_identity_service)]) -> list[AgentPermissionResponse]:
    try: return [AgentPermissionResponse.model_validate(i) for i in service.list_permissions(company_id=company_id, agent_id=agent_id)]
    except AgentNotFoundError as exc: _error(exc)


@router.post("/companies/{company_id}/agents/{agent_id}/permissions", response_model=AgentPermissionResponse, status_code=201)
def grant_permission(company_id: UUID, agent_id: UUID, data: AgentPermissionCreate, context: Annotated[ActiveCompanyContext, Depends(require_agents_manage)], service: Annotated[AgentIdentityService, Depends(get_agent_identity_service)]) -> AgentPermissionResponse:
    try: item = service.grant_permission(company_id=company_id, agent_id=agent_id, permission_key=data.permission_key, reason=data.grant_reason, actor=context.administrator, membership=context.membership)
    except (AgentNotFoundError, AgentConflictError, AgentAuthorizationError, AgentLifecycleError) as exc: _error(exc)
    return AgentPermissionResponse.model_validate(item)


@router.post("/companies/{company_id}/agents/{agent_id}/permissions/{permission_id}/revoke", response_model=AgentPermissionResponse)
def revoke_permission(company_id: UUID, agent_id: UUID, permission_id: UUID, data: AgentReason, context: Annotated[ActiveCompanyContext, Depends(require_agents_manage)], service: Annotated[AgentIdentityService, Depends(get_agent_identity_service)]) -> AgentPermissionResponse:
    try: item = service.revoke_permission(company_id=company_id, agent_id=agent_id, permission_id=permission_id, reason=data.reason, actor=context.administrator, membership=context.membership)
    except (AgentNotFoundError, AgentPermissionNotFoundError, AgentAuthorizationError, AgentLifecycleError) as exc: _error(exc)
    return AgentPermissionResponse.model_validate(item)
