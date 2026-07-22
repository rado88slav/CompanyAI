"""Company-isolated persistence for agent identities and credentials."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.agent import Agent, AgentCredential, AgentPermission


class AgentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_agent(self, **values: object) -> Agent:
        item = Agent(**values); self._session.add(item); self._session.flush(); self._session.refresh(item); return item

    def get_agent(self, *, company_id: UUID, agent_id: UUID, for_update: bool = False) -> Agent | None:
        statement = select(Agent).where(Agent.company_id == company_id, Agent.id == agent_id)
        if for_update: statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_agent_by_id(self, agent_id: UUID) -> Agent | None:
        return self._session.get(Agent, agent_id)

    def get_by_slug(self, *, company_id: UUID, slug: str) -> Agent | None:
        return self._session.scalar(select(Agent).where(Agent.company_id == company_id, Agent.slug == slug))

    def list_agents(self, *, company_id: UUID, status: str | None, agent_type: str | None, search: str | None, limit: int, offset: int) -> list[Agent]:
        statement = self._agent_filters(company_id=company_id, status=status, agent_type=agent_type, search=search)
        return list(self._session.scalars(statement.order_by(Agent.created_at.desc(), Agent.id.desc()).limit(limit).offset(offset)).all())

    def count_agents(self, *, company_id: UUID, status: str | None, agent_type: str | None, search: str | None) -> int:
        filtered = self._agent_filters(company_id=company_id, status=status, agent_type=agent_type, search=search)
        return int(self._session.scalar(select(func.count()).select_from(filtered.subquery())) or 0)

    @staticmethod
    def _agent_filters(*, company_id: UUID, status: str | None, agent_type: str | None, search: str | None):
        statement = select(Agent).where(Agent.company_id == company_id)
        if status is not None: statement = statement.where(Agent.status == status)
        if agent_type is not None: statement = statement.where(Agent.agent_type == agent_type)
        if search: statement = statement.where(or_(Agent.name.ilike(f"%{search}%"), Agent.slug.ilike(f"%{search}%")))
        return statement

    def save_agent(self, item: Agent) -> Agent:
        self._session.flush(); self._session.refresh(item); return item

    def create_credential(self, **values: object) -> AgentCredential:
        item = AgentCredential(**values); self._session.add(item); self._session.flush(); self._session.refresh(item); return item

    def get_credential(self, *, company_id: UUID, agent_id: UUID, credential_id: UUID, for_update: bool = False) -> AgentCredential | None:
        statement = select(AgentCredential).where(AgentCredential.company_id == company_id, AgentCredential.agent_id == agent_id, AgentCredential.id == credential_id)
        if for_update: statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_credential_by_public_id(self, public_id: str) -> AgentCredential | None:
        return self._session.scalar(select(AgentCredential).where(AgentCredential.public_id == public_id))

    def list_credentials(self, *, company_id: UUID, agent_id: UUID) -> list[AgentCredential]:
        return list(self._session.scalars(select(AgentCredential).where(AgentCredential.company_id == company_id, AgentCredential.agent_id == agent_id).order_by(AgentCredential.created_at.desc(), AgentCredential.id.desc())).all())

    def list_active_credentials(self, *, company_id: UUID, agent_id: UUID) -> list[AgentCredential]:
        return list(self._session.scalars(select(AgentCredential).where(AgentCredential.company_id == company_id, AgentCredential.agent_id == agent_id, AgentCredential.status == "active").with_for_update()).all())

    def save_credential(self, item: AgentCredential) -> AgentCredential:
        self._session.flush(); self._session.refresh(item); return item

    def create_permission(self, **values: object) -> AgentPermission:
        item = AgentPermission(**values); self._session.add(item); self._session.flush(); self._session.refresh(item); return item

    def get_permission(self, *, company_id: UUID, agent_id: UUID, permission_id: UUID, for_update: bool = False) -> AgentPermission | None:
        statement = select(AgentPermission).where(AgentPermission.company_id == company_id, AgentPermission.agent_id == agent_id, AgentPermission.id == permission_id)
        if for_update: statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_active_permission(self, *, company_id: UUID, agent_id: UUID, permission_key: str) -> AgentPermission | None:
        return self._session.scalar(select(AgentPermission).where(AgentPermission.company_id == company_id, AgentPermission.agent_id == agent_id, AgentPermission.permission_key == permission_key, AgentPermission.status == "active"))

    def list_permissions(self, *, company_id: UUID, agent_id: UUID, active_only: bool = False) -> list[AgentPermission]:
        statement = select(AgentPermission).where(AgentPermission.company_id == company_id, AgentPermission.agent_id == agent_id)
        if active_only: statement = statement.where(AgentPermission.status == "active")
        return list(self._session.scalars(statement.order_by(AgentPermission.created_at.desc(), AgentPermission.id.desc())).all())

    def list_active_permissions_for_update(self, *, company_id: UUID, agent_id: UUID) -> list[AgentPermission]:
        return list(self._session.scalars(select(AgentPermission).where(AgentPermission.company_id == company_id, AgentPermission.agent_id == agent_id, AgentPermission.status == "active").with_for_update()).all())

    def save_permission(self, item: AgentPermission) -> AgentPermission:
        self._session.flush(); self._session.refresh(item); return item
