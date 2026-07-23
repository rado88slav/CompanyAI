"""Administrator and authenticated-agent Tool Registry APIs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.agent_authentication import require_current_agent
from app.api.dependencies.authentication import require_current_administrator
from app.api.dependencies.company_authorization import require_platform_superuser, require_tools_manage, require_tools_read
from app.core.tool_registry import validate_tool_key
from app.models.administrator import Administrator
from app.models.tool_registry import CompanyToolStatus, ToolStatus
from app.schemas.company_context import ActiveCompanyContext
from app.schemas.tool_registry import AgentToolGrantResponse, CompanyToolListResponse, CompanyToolResponse, EffectiveToolListResponse, EffectiveToolResponse, ToolDefinitionCreate, ToolDefinitionListResponse, ToolDefinitionResponse, ToolDefinitionUpdate
from app.services.agent_identity import AuthenticatedAgent
from app.services.tool_registry import AgentToolGrantNotFoundError, CompanyToolNotFoundError, ToolAuthorizationError, ToolConflictError, ToolLifecycleError, ToolNotFoundError, ToolRegistryService, get_tool_registry_service

router = APIRouter(tags=["tool-registry"])


def _raise_tool_error(exc: Exception) -> None:
    if isinstance(exc, (ToolNotFoundError, CompanyToolNotFoundError, AgentToolGrantNotFoundError)):
        raise HTTPException(status_code=404, detail="Tool Registry resource was not found.") from exc
    if isinstance(exc, ToolAuthorizationError):
        raise HTTPException(status_code=403, detail="Insufficient tool permission.") from exc
    if isinstance(exc, (ToolConflictError, ToolLifecycleError)):
        raise HTTPException(status_code=409, detail="Tool operation conflicts with current state.") from exc
    raise exc


def _company_response(item, service: ToolRegistryService) -> CompanyToolResponse:
    response = CompanyToolResponse.model_validate(item)
    return response.model_copy(update={"tool": ToolDefinitionResponse.model_validate(service.get_tool(item.tool_definition_id))})


def _grant_response(item, service: ToolRegistryService) -> AgentToolGrantResponse:
    response = AgentToolGrantResponse.model_validate(item)
    return response.model_copy(update={"tool": ToolDefinitionResponse.model_validate(service.get_tool(item.tool_definition_id))})


def _effective_response(item) -> EffectiveToolResponse:
    return EffectiveToolResponse(
        tool=ToolDefinitionResponse.model_validate(item.tool),
        grant_id=item.grant.id,
        runtime_registered=item.runtime_registered,
        authorization_action=f"tool.execute.{item.tool.key}",
    )


@router.post("/tools", response_model=ToolDefinitionResponse, status_code=status.HTTP_201_CREATED)
def create_tool(data: ToolDefinitionCreate, administrator: Annotated[Administrator, Depends(require_platform_superuser)], service: Annotated[ToolRegistryService, Depends(get_tool_registry_service)]) -> ToolDefinitionResponse:
    try:
        return ToolDefinitionResponse.model_validate(service.create_tool(data=data, actor=administrator))
    except (ToolAuthorizationError, ToolConflictError) as exc:
        _raise_tool_error(exc)


@router.get("/tools", response_model=ToolDefinitionListResponse)
def list_tools(_administrator: Annotated[Administrator, Depends(require_current_administrator)], service: Annotated[ToolRegistryService, Depends(get_tool_registry_service)], tool_status: ToolStatus | None = Query(default=None, alias="status"), category: str | None = Query(default=None, min_length=1, max_length=100), search: str | None = Query(default=None, min_length=1, max_length=100), limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)) -> ToolDefinitionListResponse:
    items, total = service.list_tools(status=tool_status.value if tool_status else None, category=category, search=search, limit=limit, offset=offset)
    return ToolDefinitionListResponse(items=[ToolDefinitionResponse.model_validate(item) for item in items], total=total, limit=limit, offset=offset)


@router.get("/tools/{tool_id}", response_model=ToolDefinitionResponse)
def get_tool(tool_id: UUID, _administrator: Annotated[Administrator, Depends(require_current_administrator)], service: Annotated[ToolRegistryService, Depends(get_tool_registry_service)]) -> ToolDefinitionResponse:
    try:
        return ToolDefinitionResponse.model_validate(service.get_tool(tool_id))
    except ToolNotFoundError as exc:
        _raise_tool_error(exc)


@router.patch("/tools/{tool_id}", response_model=ToolDefinitionResponse)
def update_tool(tool_id: UUID, data: ToolDefinitionUpdate, administrator: Annotated[Administrator, Depends(require_platform_superuser)], service: Annotated[ToolRegistryService, Depends(get_tool_registry_service)]) -> ToolDefinitionResponse:
    try:
        return ToolDefinitionResponse.model_validate(service.update_tool(tool_id=tool_id, data=data, actor=administrator))
    except (ToolNotFoundError, ToolAuthorizationError, ToolLifecycleError) as exc:
        _raise_tool_error(exc)


def _set_tool_status(tool_id: UUID, target: str, administrator: Administrator, service: ToolRegistryService) -> ToolDefinitionResponse:
    try:
        return ToolDefinitionResponse.model_validate(service.set_tool_status(tool_id=tool_id, target=target, actor=administrator))
    except (ToolNotFoundError, ToolAuthorizationError, ToolLifecycleError) as exc:
        _raise_tool_error(exc)


@router.post("/tools/{tool_id}/activate", response_model=ToolDefinitionResponse)
def activate_tool(tool_id: UUID, administrator: Annotated[Administrator, Depends(require_platform_superuser)], service: Annotated[ToolRegistryService, Depends(get_tool_registry_service)]) -> ToolDefinitionResponse:
    return _set_tool_status(tool_id, "active", administrator, service)


@router.post("/tools/{tool_id}/deactivate", response_model=ToolDefinitionResponse)
def deactivate_tool(tool_id: UUID, administrator: Annotated[Administrator, Depends(require_platform_superuser)], service: Annotated[ToolRegistryService, Depends(get_tool_registry_service)]) -> ToolDefinitionResponse:
    return _set_tool_status(tool_id, "inactive", administrator, service)


@router.post("/tools/{tool_id}/deprecate", response_model=ToolDefinitionResponse)
def deprecate_tool(tool_id: UUID, administrator: Annotated[Administrator, Depends(require_platform_superuser)], service: Annotated[ToolRegistryService, Depends(get_tool_registry_service)]) -> ToolDefinitionResponse:
    return _set_tool_status(tool_id, "deprecated", administrator, service)


@router.get("/companies/{company_id}/tools", response_model=CompanyToolListResponse)
def list_company_tools(company_id: UUID, _context: Annotated[ActiveCompanyContext, Depends(require_tools_read)], service: Annotated[ToolRegistryService, Depends(get_tool_registry_service)], company_status: CompanyToolStatus | None = Query(default=None, alias="status"), limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)) -> CompanyToolListResponse:
    items, total = service.list_company_tools(company_id=company_id, status=company_status.value if company_status else None, limit=limit, offset=offset)
    return CompanyToolListResponse(items=[_company_response(item, service) for item in items], total=total, limit=limit, offset=offset)


@router.get("/companies/{company_id}/tools/{tool_id}", response_model=CompanyToolResponse)
def get_company_tool(company_id: UUID, tool_id: UUID, _context: Annotated[ActiveCompanyContext, Depends(require_tools_read)], service: Annotated[ToolRegistryService, Depends(get_tool_registry_service)]) -> CompanyToolResponse:
    try:
        return _company_response(service.get_company_tool(company_id=company_id, tool_id=tool_id), service)
    except (CompanyToolNotFoundError, ToolNotFoundError) as exc:
        _raise_tool_error(exc)


@router.post("/companies/{company_id}/tools/{tool_id}/enable", response_model=CompanyToolResponse)
def enable_company_tool(company_id: UUID, tool_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_tools_manage)], service: Annotated[ToolRegistryService, Depends(get_tool_registry_service)]) -> CompanyToolResponse:
    try:
        return _company_response(service.enable_company_tool(company_id=company_id, tool_id=tool_id, actor=context.administrator), service)
    except (ToolNotFoundError, ToolAuthorizationError, ToolConflictError, ToolLifecycleError) as exc:
        _raise_tool_error(exc)


@router.post("/companies/{company_id}/tools/{tool_id}/disable", response_model=CompanyToolResponse)
def disable_company_tool(company_id: UUID, tool_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_tools_manage)], service: Annotated[ToolRegistryService, Depends(get_tool_registry_service)]) -> CompanyToolResponse:
    try:
        return _company_response(service.disable_company_tool(company_id=company_id, tool_id=tool_id, actor=context.administrator), service)
    except (ToolNotFoundError, CompanyToolNotFoundError, ToolAuthorizationError) as exc:
        _raise_tool_error(exc)


@router.get("/companies/{company_id}/agents/{agent_id}/tools", response_model=list[AgentToolGrantResponse])
def list_agent_tools(company_id: UUID, agent_id: UUID, _context: Annotated[ActiveCompanyContext, Depends(require_tools_read)], service: Annotated[ToolRegistryService, Depends(get_tool_registry_service)]) -> list[AgentToolGrantResponse]:
    try:
        return [_grant_response(item, service) for item in service.list_grants(company_id=company_id, agent_id=agent_id)]
    except (AgentToolGrantNotFoundError, ToolNotFoundError) as exc:
        _raise_tool_error(exc)


@router.post("/companies/{company_id}/agents/{agent_id}/tools/{tool_id}/grant", response_model=AgentToolGrantResponse, status_code=status.HTTP_201_CREATED)
def grant_agent_tool(company_id: UUID, agent_id: UUID, tool_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_tools_manage)], service: Annotated[ToolRegistryService, Depends(get_tool_registry_service)]) -> AgentToolGrantResponse:
    try:
        item = service.grant_tool(company_id=company_id, agent_id=agent_id, tool_id=tool_id, actor=context.administrator, membership=context.membership)
        return _grant_response(item, service)
    except (AgentToolGrantNotFoundError, ToolAuthorizationError, ToolConflictError, ToolLifecycleError, ToolNotFoundError) as exc:
        _raise_tool_error(exc)


@router.post("/companies/{company_id}/agents/{agent_id}/tool-grants/{grant_id}/revoke", response_model=AgentToolGrantResponse)
def revoke_agent_tool(company_id: UUID, agent_id: UUID, grant_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_tools_manage)], service: Annotated[ToolRegistryService, Depends(get_tool_registry_service)]) -> AgentToolGrantResponse:
    try:
        item = service.revoke_grant(company_id=company_id, agent_id=agent_id, grant_id=grant_id, actor=context.administrator, membership=context.membership)
        return _grant_response(item, service)
    except (AgentToolGrantNotFoundError, ToolAuthorizationError, ToolLifecycleError, ToolNotFoundError) as exc:
        _raise_tool_error(exc)


@router.get("/internal/tools", response_model=EffectiveToolListResponse)
def list_effective_tools(identity: Annotated[AuthenticatedAgent, Depends(require_current_agent)], service: Annotated[ToolRegistryService, Depends(get_tool_registry_service)]) -> EffectiveToolListResponse:
    return EffectiveToolListResponse(items=[_effective_response(item) for item in service.effective_tools(identity)])


@router.get("/internal/tools/{tool_key}", response_model=EffectiveToolResponse)
def get_effective_tool(tool_key: str, identity: Annotated[AuthenticatedAgent, Depends(require_current_agent)], service: Annotated[ToolRegistryService, Depends(get_tool_registry_service)]) -> EffectiveToolResponse:
    try:
        validate_tool_key(tool_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Effective tool was not found.") from exc
    item = service.effective_tool(identity, tool_key)
    if item is None:
        raise HTTPException(status_code=404, detail="Effective tool was not found.")
    return _effective_response(item)
