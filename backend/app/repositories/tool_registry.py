"""Persistence queries for global tools, company availability and agent grants."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.company import Company
from app.models.tool_registry import AgentToolGrant, CompanyTool, ToolDefinition


class ToolRegistryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_tool(self, **values: object) -> ToolDefinition:
        item = ToolDefinition(**values)
        self._session.add(item)
        self._session.flush()
        self._session.refresh(item)
        return item

    def get_tool(self, tool_id: UUID, *, for_update: bool = False) -> ToolDefinition | None:
        statement = select(ToolDefinition).where(ToolDefinition.id == tool_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_tool_by_key(self, key: str) -> ToolDefinition | None:
        return self._session.scalar(select(ToolDefinition).where(ToolDefinition.key == key))

    def _tool_filters(self, *, status: str | None, category: str | None, search: str | None):
        statement = select(ToolDefinition)
        if status:
            statement = statement.where(ToolDefinition.status == status)
        if category:
            statement = statement.where(ToolDefinition.category == category)
        if search:
            statement = statement.where(or_(ToolDefinition.key.ilike(f"%{search}%"), ToolDefinition.display_name.ilike(f"%{search}%")))
        return statement

    def list_tools(self, *, status: str | None, category: str | None, search: str | None, limit: int, offset: int) -> list[ToolDefinition]:
        statement = self._tool_filters(status=status, category=category, search=search)
        return list(self._session.scalars(statement.order_by(ToolDefinition.key).limit(limit).offset(offset)).all())

    def count_tools(self, *, status: str | None, category: str | None, search: str | None) -> int:
        statement = self._tool_filters(status=status, category=category, search=search)
        return int(self._session.scalar(select(func.count()).select_from(statement.subquery())) or 0)

    def save_tool(self, item: ToolDefinition) -> ToolDefinition:
        self._session.flush()
        self._session.refresh(item)
        return item

    def get_company_tool(self, *, company_id: UUID, tool_id: UUID, for_update: bool = False) -> CompanyTool | None:
        statement = select(CompanyTool).where(CompanyTool.company_id == company_id, CompanyTool.tool_definition_id == tool_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def create_company_tool(self, **values: object) -> CompanyTool:
        item = CompanyTool(**values)
        self._session.add(item)
        self._session.flush()
        self._session.refresh(item)
        return item

    def list_company_tools(self, *, company_id: UUID, status: str | None, limit: int, offset: int) -> list[CompanyTool]:
        statement = select(CompanyTool).where(CompanyTool.company_id == company_id)
        if status:
            statement = statement.where(CompanyTool.status == status)
        return list(self._session.scalars(statement.order_by(CompanyTool.created_at.desc(), CompanyTool.id.desc()).limit(limit).offset(offset)).all())

    def count_company_tools(self, *, company_id: UUID, status: str | None) -> int:
        statement = select(func.count()).select_from(CompanyTool).where(CompanyTool.company_id == company_id)
        if status:
            statement = statement.where(CompanyTool.status == status)
        return int(self._session.scalar(statement) or 0)

    def save_company_tool(self, item: CompanyTool) -> CompanyTool:
        self._session.flush()
        self._session.refresh(item)
        return item

    def get_company(self, company_id: UUID) -> Company | None:
        return self._session.get(Company, company_id)

    def get_agent(self, *, company_id: UUID, agent_id: UUID, for_update: bool = False) -> Agent | None:
        statement = select(Agent).where(Agent.company_id == company_id, Agent.id == agent_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_active_grant(self, *, company_id: UUID, agent_id: UUID, tool_id: UUID) -> AgentToolGrant | None:
        return self._session.scalar(select(AgentToolGrant).where(AgentToolGrant.company_id == company_id, AgentToolGrant.agent_id == agent_id, AgentToolGrant.tool_definition_id == tool_id, AgentToolGrant.status == "active"))

    def create_grant(self, **values: object) -> AgentToolGrant:
        item = AgentToolGrant(**values)
        self._session.add(item)
        self._session.flush()
        self._session.refresh(item)
        return item

    def get_grant(self, *, company_id: UUID, agent_id: UUID, grant_id: UUID, for_update: bool = False) -> AgentToolGrant | None:
        statement = select(AgentToolGrant).where(AgentToolGrant.company_id == company_id, AgentToolGrant.agent_id == agent_id, AgentToolGrant.id == grant_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def list_grants(self, *, company_id: UUID, agent_id: UUID) -> list[AgentToolGrant]:
        return list(self._session.scalars(select(AgentToolGrant).where(AgentToolGrant.company_id == company_id, AgentToolGrant.agent_id == agent_id).order_by(AgentToolGrant.created_at.desc(), AgentToolGrant.id.desc())).all())

    def save_grant(self, item: AgentToolGrant) -> AgentToolGrant:
        self._session.flush()
        self._session.refresh(item)
        return item

    def list_effective_grants(self, *, company_id: UUID, agent_id: UUID) -> list[tuple[AgentToolGrant, ToolDefinition]]:
        statement = (
            select(AgentToolGrant, ToolDefinition)
            .join(ToolDefinition, ToolDefinition.id == AgentToolGrant.tool_definition_id)
            .join(CompanyTool, (CompanyTool.company_id == AgentToolGrant.company_id) & (CompanyTool.tool_definition_id == AgentToolGrant.tool_definition_id))
            .where(
                AgentToolGrant.company_id == company_id,
                AgentToolGrant.agent_id == agent_id,
                AgentToolGrant.status == "active",
                CompanyTool.status == "enabled",
                ToolDefinition.status == "active",
            )
            .order_by(ToolDefinition.key)
        )
        return list(self._session.execute(statement).tuples().all())
