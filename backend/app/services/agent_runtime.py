"""Safe internal agent runtime boundary for deterministic read-only tools."""

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.tool_registry import RuntimeToolRegistry, runtime_tool_registry, validate_tool_key
from app.db.session import get_db_session
from app.models.administrator import Administrator
from app.models.audit_log import AuditAction
from app.repositories.audit_log import AuditLogRepository
from app.repositories.dashboard import DashboardRepository
from app.repositories.tool_registry import ToolRegistryRepository
from app.schemas.agent_runtime import AgentRuntimeToolBootstrapResponse, AgentRuntimeToolResponse, AgentToolInvokeResponse
from app.schemas.dashboard import DashboardSummaryResponse
from app.services.audit_log import AuditLogService
from app.services.dashboard import DashboardService


class AgentRuntimeNotFoundError(Exception):
    pass


class AgentRuntimeUnavailableError(Exception):
    pass


class AgentRuntimeInputError(Exception):
    pass


class AgentRuntimeService:
    def __init__(
        self,
        *,
        tool_repository: ToolRegistryRepository,
        dashboard: DashboardService,
        audit: AuditLogService,
        session: Session,
        descriptors: RuntimeToolRegistry = runtime_tool_registry,
    ) -> None:
        self._tool_repository = tool_repository
        self._dashboard = dashboard
        self._audit = audit
        self._session = session
        self._descriptors = descriptors

    def list_tools(self, *, company_id: UUID) -> list[AgentRuntimeToolResponse]:
        items = []
        for tool in self._tool_repository.list_tools(
            status="active",
            category="dashboard",
            search=None,
            limit=100,
            offset=0,
        ):
            descriptor = self._descriptors.get(tool.key)
            if descriptor is None or descriptor.execution_mode != "internal":
                continue
            company_tool = self._tool_repository.get_company_tool(
                company_id=company_id,
                tool_id=tool.id,
            )
            items.append(
                AgentRuntimeToolResponse(
                    key=tool.key,
                    display_name=tool.display_name,
                    description=tool.description,
                    category=tool.category,
                    risk_level=tool.risk_level,
                    requires_approval=tool.requires_approval,
                    runtime_registered=True,
                    company_enabled=company_tool is not None
                    and company_tool.status == "enabled",
                )
            )
        return items

    def bootstrap_dashboard_summary_tool(
        self,
        *,
        company_id: UUID,
        actor: Administrator,
        app_environment: str,
    ) -> AgentRuntimeToolBootstrapResponse:
        if app_environment != "development":
            raise AgentRuntimeUnavailableError
        now = datetime.now(UTC)
        tool = self._tool_repository.get_tool_by_key("dashboard.summary.read")
        try:
            if tool is None:
                tool = self._tool_repository.create_tool(
                    key="dashboard.summary.read",
                    display_name="Read dashboard summary",
                    description="Return the safe read-only dashboard summary for the active company.",
                    category="dashboard",
                    risk_level="low",
                    execution_mode="internal",
                    requires_approval=False,
                    status="active",
                    input_schema={},
                    output_schema={"type": "object"},
                    metadata_={"runtime": "agent_runtime"},
                    is_system=True,
                    created_by_administrator_id=actor.id,
                )
                self._audit.append_platform_event(
                    actor_administrator_id=actor.id,
                    action=AuditAction.TOOL_DEFINITION_CREATED.value,
                    resource_type="tool_definition",
                    resource_id=tool.id,
                    details={"tool_key": tool.key, "status": tool.status, "risk_level": tool.risk_level},
                )
            company_tool = self._tool_repository.get_company_tool(
                company_id=company_id,
                tool_id=tool.id,
                for_update=True,
            )
            if company_tool is None:
                company_tool = self._tool_repository.create_company_tool(
                    company_id=company_id,
                    tool_definition_id=tool.id,
                    status="enabled",
                    enabled_by_administrator_id=actor.id,
                    enabled_at=now,
                )
                self._audit.append_company_event(
                    company_id=company_id,
                    actor_administrator_id=actor.id,
                    action=AuditAction.COMPANY_TOOL_ENABLED.value,
                    resource_type="company_tool",
                    resource_id=company_tool.id,
                    details={"tool_definition_id": str(tool.id), "tool_key": tool.key},
                )
            elif company_tool.status != "enabled":
                company_tool.status = "enabled"
                company_tool.enabled_by_administrator_id = actor.id
                company_tool.enabled_at = now
                company_tool.disabled_by_administrator_id = None
                company_tool.disabled_at = None
                self._tool_repository.save_company_tool(company_tool)
                self._audit.append_company_event(
                    company_id=company_id,
                    actor_administrator_id=actor.id,
                    action=AuditAction.COMPANY_TOOL_ENABLED.value,
                    resource_type="company_tool",
                    resource_id=company_tool.id,
                    details={"tool_definition_id": str(tool.id), "tool_key": tool.key},
                )
            self._session.commit()
            return AgentRuntimeToolBootstrapResponse(
                tool_id=tool.id,
                company_tool_id=company_tool.id,
                tool_key=tool.key,
                company_enabled=company_tool.status == "enabled",
            )
        except Exception:
            self._session.rollback()
            raise

    def invoke_tool(
        self,
        *,
        company_id: UUID,
        tool_key: str,
        input_data: dict[str, Any],
        actor: Administrator,
    ) -> AgentToolInvokeResponse:
        try:
            key = validate_tool_key(tool_key)
        except ValueError as exc:
            raise AgentRuntimeNotFoundError from exc
        descriptor = self._descriptors.get(key)
        if descriptor is None or descriptor.execution_mode != "internal":
            raise AgentRuntimeNotFoundError
        tool = self._tool_repository.get_tool_by_key(key)
        if tool is None or tool.status != "active" or tool.execution_mode != "internal":
            raise AgentRuntimeUnavailableError
        company_tool = self._tool_repository.get_company_tool(
            company_id=company_id,
            tool_id=tool.id,
        )
        if company_tool is None or company_tool.status != "enabled":
            raise AgentRuntimeUnavailableError
        if input_data:
            raise AgentRuntimeInputError
        if key != "dashboard.summary.read":
            raise AgentRuntimeNotFoundError

        summary = self._dashboard.get_summary(company_id=company_id)
        event = self._audit.append_company_event(
            company_id=company_id,
            actor_administrator_id=actor.id,
            action=AuditAction.AGENT_TOOL_INVOKED.value,
            resource_type="tool_definition",
            resource_id=tool.id,
            details={
                "tool_key": key,
                "execution_mode": descriptor.execution_mode,
                "result_status": "succeeded",
            },
        )
        self._session.commit()
        return AgentToolInvokeResponse(
            tool_key=key,
            status="succeeded",
            executed_at=event.created_at,
            audit_event_id=event.id,
            result=summary.model_dump(mode="json"),
        )


def get_agent_runtime_service(
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AgentRuntimeService:
    return AgentRuntimeService(
        tool_repository=ToolRegistryRepository(session),
        dashboard=DashboardService(
            repository=DashboardRepository(session),
            settings=settings,
        ),
        audit=AuditLogService(AuditLogRepository(session)),
        session=session,
    )
