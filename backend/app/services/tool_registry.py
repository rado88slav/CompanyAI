"""Transactional Tool Registry lifecycle and effective-access service."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.agent_authentication import authorization_action_for_agent
from app.core.tool_registry import RuntimeToolRegistry, runtime_tool_registry
from app.db.session import get_db_session
from app.models.administrator import Administrator
from app.models.agent import Agent
from app.models.audit_log import AuditAction
from app.models.company_membership import CompanyMembership, CompanyRole
from app.models.tool_registry import AgentToolGrant, CompanyTool, ToolDefinition
from app.repositories.audit_log import AuditLogRepository
from app.repositories.tool_registry import ToolRegistryRepository
from app.schemas.approval import AuthorizationAction
from app.schemas.tool_registry import ToolDefinitionCreate, ToolDefinitionUpdate
from app.services.agent_identity import AuthenticatedAgent
from app.services.audit_log import AuditLogService


class ToolNotFoundError(Exception):
    pass


class ToolConflictError(Exception):
    pass


class ToolAuthorizationError(Exception):
    pass


class ToolLifecycleError(Exception):
    pass


class CompanyToolNotFoundError(Exception):
    pass


class AgentToolGrantNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class EffectiveTool:
    tool: ToolDefinition
    grant: AgentToolGrant
    runtime_registered: bool


def tool_authorization_action(identity: AuthenticatedAgent, tool: ToolDefinition) -> AuthorizationAction:
    """Derive exact future Approval Manager input from trusted persisted state."""

    return authorization_action_for_agent(
        identity,
        action_type=f"tool.execute.{tool.key}",
        tool_identifier=tool.key,
        risk_level=tool.risk_level,
        scope_type="company",
        scope_id=identity.agent.company_id,
        target_resource_type="tool_definition",
        target_resource_id=tool.id,
    )


class ToolRegistryService:
    def __init__(self, repository: ToolRegistryRepository, audit: AuditLogService, session: Session, descriptors: RuntimeToolRegistry = runtime_tool_registry) -> None:
        self._repository = repository
        self._audit = audit
        self._session = session
        self._descriptors = descriptors

    def _tool(self, tool_id: UUID, *, for_update: bool = False) -> ToolDefinition:
        item = self._repository.get_tool(tool_id, for_update=for_update)
        if item is None:
            raise ToolNotFoundError
        return item

    @staticmethod
    def _protect_system_agent(agent: Agent, actor: Administrator, membership: CompanyMembership | None) -> None:
        is_owner = membership is not None and membership.role == CompanyRole.OWNER.value
        if agent.is_system and not (actor.is_superuser or is_owner):
            raise ToolAuthorizationError

    def create_tool(self, *, data: ToolDefinitionCreate, actor: Administrator) -> ToolDefinition:
        if not actor.is_superuser:
            raise ToolAuthorizationError
        if self._repository.get_tool_by_key(data.key) is not None:
            raise ToolConflictError
        try:
            item = self._repository.create_tool(
                key=data.key,
                display_name=data.display_name,
                description=data.description,
                category=data.category,
                risk_level=data.risk_level.value,
                execution_mode=data.execution_mode.value,
                requires_approval=data.requires_approval,
                status=data.status.value,
                input_schema=data.input_schema,
                output_schema=data.output_schema,
                metadata_=data.metadata,
                is_system=data.is_system,
                created_by_administrator_id=actor.id,
            )
            self._audit.append_platform_event(actor_administrator_id=actor.id, action=AuditAction.TOOL_DEFINITION_CREATED.value, resource_type="tool_definition", resource_id=item.id, details={"tool_key": item.key, "status": item.status, "risk_level": item.risk_level})
            self._session.commit()
            return item
        except IntegrityError as exc:
            self._session.rollback()
            raise ToolConflictError from exc
        except Exception:
            self._session.rollback()
            raise

    def list_tools(self, *, status: str | None, category: str | None, search: str | None, limit: int, offset: int) -> tuple[list[ToolDefinition], int]:
        filters = {"status": status, "category": category, "search": search}
        return self._repository.list_tools(**filters, limit=limit, offset=offset), self._repository.count_tools(**filters)

    def get_tool(self, tool_id: UUID) -> ToolDefinition:
        return self._tool(tool_id)

    def update_tool(self, *, tool_id: UUID, data: ToolDefinitionUpdate, actor: Administrator) -> ToolDefinition:
        if not actor.is_superuser:
            raise ToolAuthorizationError
        item = self._tool(tool_id, for_update=True)
        if item.status == "deprecated":
            raise ToolLifecycleError
        changes = data.model_dump(exclude_unset=True)
        for enum_field in ("risk_level", "execution_mode"):
            if enum_field in changes:
                changes[enum_field] = changes[enum_field].value
        if "metadata" in changes:
            changes["metadata_"] = changes.pop("metadata")
        resulting_risk = changes.get("risk_level", item.risk_level)
        resulting_approval = changes.get("requires_approval", item.requires_approval)
        if resulting_risk in {"high", "critical"} and not resulting_approval:
            raise ToolLifecycleError
        previous = {field: getattr(item, field) for field in changes}
        for field, value in changes.items():
            setattr(item, field, value)
        try:
            self._repository.save_tool(item)
            self._audit.append_platform_event(actor_administrator_id=actor.id, action=AuditAction.TOOL_DEFINITION_UPDATED.value, resource_type="tool_definition", resource_id=item.id, details={"tool_key": item.key, "fields": sorted(changes), "changed": any(previous[key] != changes[key] for key in changes)})
            self._session.commit()
            return item
        except Exception:
            self._session.rollback()
            raise

    def set_tool_status(self, *, tool_id: UUID, target: str, actor: Administrator) -> ToolDefinition:
        if not actor.is_superuser:
            raise ToolAuthorizationError
        item = self._tool(tool_id, for_update=True)
        if item.status == "deprecated" and target != "deprecated":
            raise ToolLifecycleError
        previous = item.status
        item.status = target
        actions = {
            "active": AuditAction.TOOL_DEFINITION_ACTIVATED,
            "inactive": AuditAction.TOOL_DEFINITION_DEACTIVATED,
            "deprecated": AuditAction.TOOL_DEFINITION_DEPRECATED,
        }
        try:
            self._repository.save_tool(item)
            self._audit.append_platform_event(actor_administrator_id=actor.id, action=actions[target].value, resource_type="tool_definition", resource_id=item.id, details={"tool_key": item.key, "previous_status": previous, "new_status": target, "changed": previous != target})
            self._session.commit()
            return item
        except Exception:
            self._session.rollback()
            raise

    def list_company_tools(self, *, company_id: UUID, status: str | None, limit: int, offset: int) -> tuple[list[CompanyTool], int]:
        return self._repository.list_company_tools(company_id=company_id, status=status, limit=limit, offset=offset), self._repository.count_company_tools(company_id=company_id, status=status)

    def get_company_tool(self, *, company_id: UUID, tool_id: UUID) -> CompanyTool:
        item = self._repository.get_company_tool(company_id=company_id, tool_id=tool_id)
        if item is None:
            raise CompanyToolNotFoundError
        return item

    def enable_company_tool(self, *, company_id: UUID, tool_id: UUID, actor: Administrator) -> CompanyTool:
        tool = self._tool(tool_id)
        if tool.is_system and not actor.is_superuser:
            raise ToolAuthorizationError
        if tool.status != "active":
            raise ToolLifecycleError
        now = datetime.now(UTC)
        item = self._repository.get_company_tool(company_id=company_id, tool_id=tool_id, for_update=True)
        try:
            if item is None:
                item = self._repository.create_company_tool(company_id=company_id, tool_definition_id=tool_id, status="enabled", enabled_by_administrator_id=actor.id, enabled_at=now)
            else:
                item.status = "enabled"
                item.enabled_by_administrator_id = actor.id
                item.enabled_at = now
                item.disabled_by_administrator_id = None
                item.disabled_at = None
                self._repository.save_company_tool(item)
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.COMPANY_TOOL_ENABLED.value, resource_type="company_tool", resource_id=item.id, details={"tool_definition_id": str(tool_id), "tool_key": tool.key})
            self._session.commit()
            return item
        except IntegrityError as exc:
            self._session.rollback()
            raise ToolConflictError from exc
        except Exception:
            self._session.rollback()
            raise

    def disable_company_tool(self, *, company_id: UUID, tool_id: UUID, actor: Administrator) -> CompanyTool:
        tool = self._tool(tool_id)
        if tool.is_system and not actor.is_superuser:
            raise ToolAuthorizationError
        item = self._repository.get_company_tool(company_id=company_id, tool_id=tool_id, for_update=True)
        if item is None:
            raise CompanyToolNotFoundError
        now = datetime.now(UTC)
        item.status = "disabled"
        item.disabled_by_administrator_id = actor.id
        item.disabled_at = now
        try:
            self._repository.save_company_tool(item)
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.COMPANY_TOOL_DISABLED.value, resource_type="company_tool", resource_id=item.id, details={"tool_definition_id": str(tool_id), "tool_key": tool.key})
            self._session.commit()
            return item
        except Exception:
            self._session.rollback()
            raise

    def list_grants(self, *, company_id: UUID, agent_id: UUID) -> list[AgentToolGrant]:
        if self._repository.get_agent(company_id=company_id, agent_id=agent_id) is None:
            raise AgentToolGrantNotFoundError
        return self._repository.list_grants(company_id=company_id, agent_id=agent_id)

    def grant_tool(self, *, company_id: UUID, agent_id: UUID, tool_id: UUID, actor: Administrator, membership: CompanyMembership | None) -> AgentToolGrant:
        agent = self._repository.get_agent(company_id=company_id, agent_id=agent_id, for_update=True)
        if agent is None:
            raise AgentToolGrantNotFoundError
        self._protect_system_agent(agent, actor, membership)
        if agent.status != "active":
            raise ToolLifecycleError
        company_tool = self._repository.get_company_tool(company_id=company_id, tool_id=tool_id, for_update=True)
        tool = self._tool(tool_id)
        if company_tool is None or company_tool.status != "enabled" or tool.status != "active":
            raise ToolLifecycleError
        if self._repository.get_active_grant(company_id=company_id, agent_id=agent_id, tool_id=tool_id):
            raise ToolConflictError
        try:
            item = self._repository.create_grant(company_id=company_id, agent_id=agent_id, tool_definition_id=tool_id, status="active", granted_by_administrator_id=actor.id, granted_at=datetime.now(UTC))
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.AGENT_TOOL_GRANTED.value, resource_type="agent_tool_grant", resource_id=item.id, details={"agent_id": str(agent_id), "tool_definition_id": str(tool_id), "tool_key": tool.key})
            self._session.commit()
            return item
        except IntegrityError as exc:
            self._session.rollback()
            raise ToolConflictError from exc
        except Exception:
            self._session.rollback()
            raise

    def revoke_grant(self, *, company_id: UUID, agent_id: UUID, grant_id: UUID, actor: Administrator, membership: CompanyMembership | None) -> AgentToolGrant:
        agent = self._repository.get_agent(company_id=company_id, agent_id=agent_id, for_update=True)
        if agent is None:
            raise AgentToolGrantNotFoundError
        self._protect_system_agent(agent, actor, membership)
        item = self._repository.get_grant(company_id=company_id, agent_id=agent_id, grant_id=grant_id, for_update=True)
        if item is None:
            raise AgentToolGrantNotFoundError
        if item.status != "active":
            raise ToolLifecycleError
        item.status = "revoked"
        item.revoked_by_administrator_id = actor.id
        item.revoked_at = datetime.now(UTC)
        try:
            self._repository.save_grant(item)
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.AGENT_TOOL_REVOKED.value, resource_type="agent_tool_grant", resource_id=item.id, details={"agent_id": str(agent_id), "tool_definition_id": str(item.tool_definition_id)})
            self._session.commit()
            return item
        except Exception:
            self._session.rollback()
            raise

    def effective_tools(self, identity: AuthenticatedAgent) -> list[EffectiveTool]:
        agent = self._repository.get_agent(company_id=identity.agent.company_id, agent_id=identity.agent.id)
        company = self._repository.get_company(identity.agent.company_id)
        expires_at = identity.credential.expires_at
        credential_expired = expires_at is not None and expires_at <= datetime.now(UTC)
        if company is None or not company.is_active or company.status != "active" or agent is None or agent.status != "active" or identity.credential.company_id != agent.company_id or identity.credential.agent_id != agent.id or identity.credential.status != "active" or credential_expired:
            return []
        return [EffectiveTool(tool=tool, grant=grant, runtime_registered=self._descriptors.is_registered(tool.key)) for grant, tool in self._repository.list_effective_grants(company_id=agent.company_id, agent_id=agent.id)]

    def effective_tool(self, identity: AuthenticatedAgent, key: str) -> EffectiveTool | None:
        return next((item for item in self.effective_tools(identity) if item.tool.key == key), None)


def get_tool_registry_service(session: Annotated[Session, Depends(get_db_session)]) -> ToolRegistryService:
    return ToolRegistryService(ToolRegistryRepository(session), AuditLogService(AuditLogRepository(session)), session)
