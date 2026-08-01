"""Administrator-facing safe preview Agent Manager APIs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.company_authorization import require_agents_manage, require_agents_read
from app.schemas.agent_manager import (
    AgentManagerAgentResponse,
    AgentManagerCreateFromTemplateRequest,
    AgentManagerInstructionsUpdate,
    AgentManagerListResponse,
    AgentManagerTemplateResponse,
    AgentPreviewTaskRequest,
    AgentPreviewTaskResponse,
    AgentPromptPreviewResponse,
)
from app.schemas.company_context import ActiveCompanyContext
from app.services.agent_manager import (
    AgentManagerConflictError,
    AgentManagerDeniedError,
    AgentManagerNotFoundError,
    AgentManagerPayloadError,
    AgentManagerService,
    PreviewRuntimeOutputError,
    PreviewRuntimeUnavailableError,
    get_agent_manager_service,
)

router = APIRouter(prefix="/companies/{company_id}/agent-manager", tags=["agent-manager"])


def _error(exc: Exception) -> None:
    if isinstance(exc, AgentManagerNotFoundError):
        raise HTTPException(404, "Agent Manager resource was not found.") from exc
    if isinstance(exc, AgentManagerDeniedError):
        raise HTTPException(403, "Agent Manager action is not allowed.") from exc
    if isinstance(exc, (AgentManagerConflictError, AgentManagerPayloadError, PreviewRuntimeOutputError)):
        raise HTTPException(409, "Agent Manager operation conflicts with current state.") from exc
    if isinstance(exc, PreviewRuntimeUnavailableError):
        raise HTTPException(503, "Agent Manager preview runtime is unavailable.") from exc
    raise exc


@router.get("/templates", response_model=list[AgentManagerTemplateResponse])
def list_agent_templates(
    _context: Annotated[ActiveCompanyContext, Depends(require_agents_read)],
    service: Annotated[AgentManagerService, Depends(get_agent_manager_service)],
) -> list[AgentManagerTemplateResponse]:
    return service.templates()


@router.get("/agents", response_model=AgentManagerListResponse)
def list_managed_agents(
    company_id: UUID,
    _context: Annotated[ActiveCompanyContext, Depends(require_agents_read)],
    service: Annotated[AgentManagerService, Depends(get_agent_manager_service)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> AgentManagerListResponse:
    return service.list_agents(company_id=company_id, limit=limit, offset=offset)


@router.post("/agents/from-template", response_model=AgentManagerAgentResponse, status_code=201)
def create_agent_from_template(
    company_id: UUID,
    data: AgentManagerCreateFromTemplateRequest,
    context: Annotated[ActiveCompanyContext, Depends(require_agents_manage)],
    service: Annotated[AgentManagerService, Depends(get_agent_manager_service)],
) -> AgentManagerAgentResponse:
    try:
        return service.create_from_template(company_id=company_id, data=data, actor=context.administrator)
    except Exception as exc:
        _error(exc)


@router.patch("/agents/{agent_id}/instructions", response_model=AgentManagerAgentResponse)
def update_agent_instructions(
    company_id: UUID,
    agent_id: UUID,
    data: AgentManagerInstructionsUpdate,
    context: Annotated[ActiveCompanyContext, Depends(require_agents_manage)],
    service: Annotated[AgentManagerService, Depends(get_agent_manager_service)],
) -> AgentManagerAgentResponse:
    try:
        return service.update_instructions(company_id=company_id, agent_id=agent_id, data=data, actor=context.administrator)
    except Exception as exc:
        _error(exc)


def _set_active(company_id: UUID, agent_id: UUID, active: bool, context: ActiveCompanyContext, service: AgentManagerService) -> AgentManagerAgentResponse:
    try:
        return service.set_active(company_id=company_id, agent_id=agent_id, active=active, actor=context.administrator)
    except Exception as exc:
        _error(exc)


@router.post("/agents/{agent_id}/activate", response_model=AgentManagerAgentResponse)
def activate_agent(
    company_id: UUID,
    agent_id: UUID,
    context: Annotated[ActiveCompanyContext, Depends(require_agents_manage)],
    service: Annotated[AgentManagerService, Depends(get_agent_manager_service)],
) -> AgentManagerAgentResponse:
    return _set_active(company_id, agent_id, True, context, service)


@router.post("/agents/{agent_id}/deactivate", response_model=AgentManagerAgentResponse)
def deactivate_agent(
    company_id: UUID,
    agent_id: UUID,
    context: Annotated[ActiveCompanyContext, Depends(require_agents_manage)],
    service: Annotated[AgentManagerService, Depends(get_agent_manager_service)],
) -> AgentManagerAgentResponse:
    return _set_active(company_id, agent_id, False, context, service)


@router.get("/agents/{agent_id}/prompt-preview", response_model=AgentPromptPreviewResponse)
def preview_agent_prompt(
    company_id: UUID,
    agent_id: UUID,
    _context: Annotated[ActiveCompanyContext, Depends(require_agents_read)],
    service: Annotated[AgentManagerService, Depends(get_agent_manager_service)],
) -> AgentPromptPreviewResponse:
    try:
        return service.prompt_preview(company_id=company_id, agent_id=agent_id)
    except Exception as exc:
        _error(exc)


@router.post("/agents/{agent_id}/preview-task", response_model=AgentPreviewTaskResponse)
def run_agent_preview_task(
    company_id: UUID,
    agent_id: UUID,
    data: AgentPreviewTaskRequest,
    context: Annotated[ActiveCompanyContext, Depends(require_agents_manage)],
    service: Annotated[AgentManagerService, Depends(get_agent_manager_service)],
) -> AgentPreviewTaskResponse:
    try:
        return service.run_task(company_id=company_id, agent_id=agent_id, data=data, actor=context.administrator)
    except Exception as exc:
        _error(exc)
