"""Administrator-facing safe agent runtime APIs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.company_authorization import require_tools_manage, require_tools_read
from app.core.config import Settings, get_settings
from app.schemas.agent_runtime import AgentRuntimeToolBootstrapResponse, AgentRuntimeToolListResponse, AgentToolInvokeRequest, AgentToolInvokeResponse
from app.schemas.company_context import ActiveCompanyContext
from app.services.agent_runtime import AgentRuntimeInputError, AgentRuntimeNotFoundError, AgentRuntimeService, AgentRuntimeUnavailableError, get_agent_runtime_service

router = APIRouter(tags=["agent-runtime"])


def _runtime_error(exc: Exception) -> None:
    if isinstance(exc, AgentRuntimeNotFoundError):
        raise HTTPException(status_code=404, detail="Agent runtime tool was not found.") from exc
    if isinstance(exc, AgentRuntimeInputError):
        raise HTTPException(status_code=422, detail="Agent runtime tool input is invalid.") from exc
    if isinstance(exc, AgentRuntimeUnavailableError):
        raise HTTPException(status_code=409, detail="Agent runtime tool is not available for this company.") from exc
    raise exc


@router.get("/companies/{company_id}/agent-runtime/tools", response_model=AgentRuntimeToolListResponse)
def list_agent_runtime_tools(
    company_id: UUID,
    _context: Annotated[ActiveCompanyContext, Depends(require_tools_read)],
    service: Annotated[AgentRuntimeService, Depends(get_agent_runtime_service)],
) -> AgentRuntimeToolListResponse:
    return AgentRuntimeToolListResponse(items=service.list_tools(company_id=company_id))


@router.post("/companies/{company_id}/agent-runtime/tools/{tool_key}/invoke", response_model=AgentToolInvokeResponse)
def invoke_agent_runtime_tool(
    company_id: UUID,
    tool_key: str,
    data: AgentToolInvokeRequest,
    context: Annotated[ActiveCompanyContext, Depends(require_tools_read)],
    service: Annotated[AgentRuntimeService, Depends(get_agent_runtime_service)],
) -> AgentToolInvokeResponse:
    try:
        return service.invoke_tool(
            company_id=company_id,
            tool_key=tool_key,
            input_data=data.input,
            actor=context.administrator,
        )
    except (AgentRuntimeInputError, AgentRuntimeNotFoundError, AgentRuntimeUnavailableError) as exc:
        _runtime_error(exc)


@router.post(
    "/companies/{company_id}/agent-runtime/tools/dashboard-summary/setup",
    response_model=AgentRuntimeToolBootstrapResponse,
    status_code=status.HTTP_201_CREATED,
)
def setup_dashboard_summary_tool(
    company_id: UUID,
    context: Annotated[ActiveCompanyContext, Depends(require_tools_manage)],
    service: Annotated[AgentRuntimeService, Depends(get_agent_runtime_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AgentRuntimeToolBootstrapResponse:
    try:
        return service.bootstrap_dashboard_summary_tool(
            company_id=company_id,
            actor=context.administrator,
            app_environment=settings.app_environment,
        )
    except AgentRuntimeUnavailableError as exc:
        _runtime_error(exc)


@router.post(
    "/companies/{company_id}/agent-runtime/tools/email-campaigns/setup",
    response_model=AgentRuntimeToolBootstrapResponse,
    status_code=status.HTTP_201_CREATED,
)
def setup_email_campaigns_tool(
    company_id: UUID,
    context: Annotated[ActiveCompanyContext, Depends(require_tools_manage)],
    service: Annotated[AgentRuntimeService, Depends(get_agent_runtime_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AgentRuntimeToolBootstrapResponse:
    try:
        return service.bootstrap_email_campaigns_tool(
            company_id=company_id,
            actor=context.administrator,
            app_environment=settings.app_environment,
        )
    except (AgentRuntimeNotFoundError, AgentRuntimeUnavailableError) as exc:
        _runtime_error(exc)
