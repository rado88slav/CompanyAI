"""Agent lifecycle, credential, permission and internal authentication services."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.agent_security import AgentTokenClaims, InvalidAgentCredentialError, InvalidAgentTokenError, create_agent_token, decode_agent_token, generate_agent_credential, parse_agent_credential, verify_agent_credential
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.models.administrator import Administrator
from app.models.agent import Agent, AgentCredential, AgentPermission
from app.models.audit_log import AuditAction
from app.models.company import CompanyStatus
from app.models.company_membership import CompanyMembership, CompanyRole
from app.repositories.agent import AgentRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.company import CompanyRepository
from app.schemas.agent import AgentCreate, AgentUpdate
from app.services.audit_log import AuditLogService


class AgentNotFoundError(Exception): pass
class AgentConflictError(Exception): pass
class AgentLifecycleError(Exception): pass
class AgentAuthorizationError(Exception): pass
class AgentCredentialNotFoundError(Exception): pass
class AgentPermissionNotFoundError(Exception): pass
class InvalidAgentAuthenticationError(Exception): pass


@dataclass(frozen=True, slots=True)
class OneTimeCredential:
    metadata: AgentCredential
    plaintext: str


@dataclass(frozen=True, slots=True)
class IssuedAgentToken:
    access_token: str
    expires_in: int
    agent: Agent
    credential: AgentCredential


@dataclass(frozen=True, slots=True)
class AuthenticatedAgent:
    agent: Agent
    credential: AgentCredential
    permissions: tuple[str, ...]


class AgentIdentityService:
    def __init__(self, repository: AgentRepository, company_repository: CompanyRepository, audit: AuditLogService, session: Session, settings: Settings) -> None:
        self._repository = repository; self._companies = company_repository; self._audit = audit; self._session = session; self._settings = settings

    @staticmethod
    def _can_manage_system(actor: Administrator, membership: CompanyMembership | None) -> bool:
        return actor.is_superuser or bool(membership and membership.role == CompanyRole.OWNER.value)

    def _get(self, company_id: UUID, agent_id: UUID, *, for_update: bool = False) -> Agent:
        agent = self._repository.get_agent(company_id=company_id, agent_id=agent_id, for_update=for_update)
        if agent is None: raise AgentNotFoundError
        return agent

    def _protect_system(self, agent: Agent, actor: Administrator, membership: CompanyMembership | None) -> None:
        if agent.is_system and not self._can_manage_system(actor, membership): raise AgentAuthorizationError

    def create_agent(self, *, company_id: UUID, data: AgentCreate, actor: Administrator, membership: CompanyMembership | None) -> Agent:
        if data.is_system and not self._can_manage_system(actor, membership): raise AgentAuthorizationError
        if self._repository.get_by_slug(company_id=company_id, slug=data.slug) is not None: raise AgentConflictError
        try:
            agent = self._repository.create_agent(company_id=company_id, name=data.name, slug=data.slug, agent_type=data.agent_type.value, description=data.description, status=data.status.value, is_system=data.is_system, metadata_=data.metadata, created_by_administrator_id=actor.id)
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.AGENT_CREATED.value, resource_type="agent", resource_id=agent.id, details={"agent_type": agent.agent_type, "status": agent.status, "is_system": agent.is_system})
            self._session.commit(); return agent
        except IntegrityError as exc: self._session.rollback(); raise AgentConflictError from exc
        except Exception: self._session.rollback(); raise

    def get_agent(self, *, company_id: UUID, agent_id: UUID) -> Agent: return self._get(company_id, agent_id)

    def list_agents(self, *, company_id: UUID, status: str | None, agent_type: str | None, search: str | None, limit: int, offset: int) -> tuple[list[Agent], int]:
        filters = dict(company_id=company_id, status=status, agent_type=agent_type, search=search)
        return self._repository.list_agents(**filters, limit=limit, offset=offset), self._repository.count_agents(**filters)

    def update_agent(self, *, company_id: UUID, agent_id: UUID, data: AgentUpdate, actor: Administrator, membership: CompanyMembership | None) -> Agent:
        agent = self._get(company_id, agent_id, for_update=True); self._protect_system(agent, actor, membership)
        changes = data.model_dump(exclude_unset=True)
        if "agent_type" in changes: changes["agent_type"] = changes["agent_type"].value
        if "metadata" in changes: changes["metadata_"] = changes.pop("metadata")
        previous = {key: getattr(agent, key) for key in changes}
        for key, value in changes.items(): setattr(agent, key, value)
        agent.updated_by_administrator_id = actor.id
        try:
            agent = self._repository.save_agent(agent)
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.AGENT_UPDATED.value, resource_type="agent", resource_id=agent.id, details={"fields": sorted(changes), "changed": any(previous[k] != changes[k] for k in changes)})
            self._session.commit(); return agent
        except Exception: self._session.rollback(); raise

    def set_active(self, *, company_id: UUID, agent_id: UUID, active: bool, actor: Administrator, membership: CompanyMembership | None) -> Agent:
        agent = self._get(company_id, agent_id, for_update=True); self._protect_system(agent, actor, membership)
        if agent.status == "revoked": raise AgentLifecycleError
        target = "active" if active else "inactive"; previous = agent.status
        if previous != target: agent.status = target; agent.auth_version += 1
        agent.updated_by_administrator_id = actor.id
        action = AuditAction.AGENT_ACTIVATED if active else AuditAction.AGENT_DEACTIVATED
        try:
            agent = self._repository.save_agent(agent)
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=action.value, resource_type="agent", resource_id=agent.id, details={"previous_status": previous, "new_status": target, "changed": previous != target})
            self._session.commit(); return agent
        except Exception: self._session.rollback(); raise

    def revoke_agent(self, *, company_id: UUID, agent_id: UUID, reason: str | None, actor: Administrator, membership: CompanyMembership | None) -> Agent:
        agent = self._get(company_id, agent_id, for_update=True)
        self._protect_system(agent, actor, membership)
        if agent.status == "revoked":
            raise AgentLifecycleError

        previous_status = agent.status
        now = datetime.now(UTC)
        credentials = self._repository.list_active_credentials(
            company_id=company_id,
            agent_id=agent_id,
        )
        permissions = self._repository.list_active_permissions_for_update(
            company_id=company_id,
            agent_id=agent_id,
        )
        try:
            for item in credentials:
                item.status = "revoked"
                item.revoked_at = now
                item.revoked_by_administrator_id = actor.id
                item.revocation_reason = "Agent revoked."
                self._repository.save_credential(item)
                self._audit.append_company_event(
                    company_id=company_id,
                    actor_administrator_id=actor.id,
                    action=AuditAction.AGENT_CREDENTIAL_REVOKED.value,
                    resource_type="agent_credential",
                    resource_id=item.id,
                    details={
                        "agent_id": str(agent_id),
                        "credential_id": str(item.id),
                        "reason": "Agent revoked.",
                    },
                )
            for item in permissions:
                item.status = "revoked"
                item.revoked_at = now
                item.revoked_by_administrator_id = actor.id
                item.revocation_reason = "Agent revoked."
                self._repository.save_permission(item)
                self._audit.append_company_event(
                    company_id=company_id,
                    actor_administrator_id=actor.id,
                    action=AuditAction.AGENT_PERMISSION_REVOKED.value,
                    resource_type="agent_permission",
                    resource_id=item.id,
                    details={
                        "agent_id": str(agent_id),
                        "permission_key": item.permission_key,
                        "reason": "Agent revoked.",
                    },
                )

            agent.status = "revoked"
            agent.revoked_at = now
            agent.revoked_by_administrator_id = actor.id
            agent.revocation_reason = reason
            agent.auth_version += 1
            self._repository.save_agent(agent)
            self._audit.append_company_event(
                company_id=company_id,
                actor_administrator_id=actor.id,
                action=AuditAction.AGENT_REVOKED.value,
                resource_type="agent",
                resource_id=agent.id,
                details={
                    "previous_status": previous_status,
                    "revoked_credentials": len(credentials),
                    "revoked_permissions": len(permissions),
                    "reason": reason,
                },
            )
            self._session.commit()
            return agent
        except Exception:
            self._session.rollback()
            raise

    def list_credentials(self, *, company_id: UUID, agent_id: UUID) -> list[AgentCredential]: self._get(company_id, agent_id); return self._repository.list_credentials(company_id=company_id, agent_id=agent_id)

    def create_credential(self, *, company_id: UUID, agent_id: UUID, name: str, expires_at: datetime | None, actor: Administrator, membership: CompanyMembership | None) -> OneTimeCredential:
        agent = self._get(company_id, agent_id, for_update=True); self._protect_system(agent, actor, membership)
        if agent.status != "active": raise AgentLifecycleError
        generated = generate_agent_credential(pepper=self._settings.agent_credential_pepper)
        try:
            item = self._repository.create_credential(company_id=company_id, agent_id=agent_id, name=name, public_id=generated.public_id, secret_hash=generated.secret_hash, secret_prefix=generated.secret_prefix, secret_last_four=generated.secret_last_four, created_by_administrator_id=actor.id, expires_at=expires_at)
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.AGENT_CREDENTIAL_CREATED.value, resource_type="agent_credential", resource_id=item.id, details={"agent_id": str(agent_id), "credential_id": str(item.id), "expires_at": expires_at.isoformat() if expires_at else None})
            self._session.commit(); return OneTimeCredential(item, generated.plaintext)
        except Exception: self._session.rollback(); raise

    def rotate_credential(self, *, company_id: UUID, agent_id: UUID, credential_id: UUID, actor: Administrator, membership: CompanyMembership | None) -> OneTimeCredential:
        agent = self._get(company_id, agent_id, for_update=True); self._protect_system(agent, actor, membership)
        old = self._repository.get_credential(company_id=company_id, agent_id=agent_id, credential_id=credential_id, for_update=True)
        if old is None: raise AgentCredentialNotFoundError
        if old.status != "active" or agent.status != "active": raise AgentLifecycleError
        generated = generate_agent_credential(pepper=self._settings.agent_credential_pepper); now = datetime.now(UTC)
        try:
            old.status="rotated"; old.revoked_at=now; old.revoked_by_administrator_id=actor.id; old.revocation_reason="Credential rotated."; self._repository.save_credential(old)
            new = self._repository.create_credential(company_id=company_id, agent_id=agent_id, name=old.name, public_id=generated.public_id, secret_hash=generated.secret_hash, secret_prefix=generated.secret_prefix, secret_last_four=generated.secret_last_four, created_by_administrator_id=actor.id, rotated_from_credential_id=old.id, expires_at=old.expires_at)
            agent.auth_version += 1; agent.updated_by_administrator_id=actor.id; self._repository.save_agent(agent)
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.AGENT_CREDENTIAL_ROTATED.value, resource_type="agent_credential", resource_id=new.id, details={"agent_id": str(agent_id), "previous_credential_id": str(old.id), "new_credential_id": str(new.id)})
            self._session.commit(); return OneTimeCredential(new, generated.plaintext)
        except Exception: self._session.rollback(); raise

    def revoke_credential(self, *, company_id: UUID, agent_id: UUID, credential_id: UUID, reason: str | None, actor: Administrator, membership: CompanyMembership | None) -> AgentCredential:
        agent = self._get(company_id, agent_id, for_update=True); self._protect_system(agent, actor, membership)
        item = self._repository.get_credential(company_id=company_id, agent_id=agent_id, credential_id=credential_id, for_update=True)
        if item is None: raise AgentCredentialNotFoundError
        if item.status != "active": raise AgentLifecycleError
        try:
            item.status="revoked"; item.revoked_at=datetime.now(UTC); item.revoked_by_administrator_id=actor.id; item.revocation_reason=reason; self._repository.save_credential(item)
            agent.auth_version += 1; self._repository.save_agent(agent)
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.AGENT_CREDENTIAL_REVOKED.value, resource_type="agent_credential", resource_id=item.id, details={"agent_id": str(agent_id), "credential_id": str(item.id), "reason": reason})
            self._session.commit(); return item
        except Exception: self._session.rollback(); raise

    def list_permissions(self, *, company_id: UUID, agent_id: UUID) -> list[AgentPermission]: self._get(company_id, agent_id); return self._repository.list_permissions(company_id=company_id, agent_id=agent_id)

    def grant_permission(self, *, company_id: UUID, agent_id: UUID, permission_key: str, reason: str | None, actor: Administrator, membership: CompanyMembership | None) -> AgentPermission:
        agent = self._get(company_id, agent_id, for_update=True)
        self._protect_system(agent, actor, membership)
        if agent.status == "revoked":
            raise AgentLifecycleError
        if self._repository.get_active_permission(
            company_id=company_id,
            agent_id=agent_id,
            permission_key=permission_key,
        ):
            raise AgentConflictError
        try:
            item = self._repository.create_permission(
                company_id=company_id,
                agent_id=agent_id,
                permission_key=permission_key,
                granted_by_administrator_id=actor.id,
                grant_reason=reason,
            )
            self._audit.append_company_event(
                company_id=company_id,
                actor_administrator_id=actor.id,
                action=AuditAction.AGENT_PERMISSION_GRANTED.value,
                resource_type="agent_permission",
                resource_id=item.id,
                details={"agent_id": str(agent_id), "permission_key": permission_key},
            )
            self._session.commit()
            return item
        except IntegrityError as exc:
            self._session.rollback()
            raise AgentConflictError from exc
        except Exception:
            self._session.rollback()
            raise

    def revoke_permission(self, *, company_id: UUID, agent_id: UUID, permission_id: UUID, reason: str | None, actor: Administrator, membership: CompanyMembership | None) -> AgentPermission:
        agent = self._get(company_id, agent_id); self._protect_system(agent, actor, membership)
        item = self._repository.get_permission(company_id=company_id, agent_id=agent_id, permission_id=permission_id, for_update=True)
        if item is None: raise AgentPermissionNotFoundError
        if item.status != "active": raise AgentLifecycleError
        try:
            item.status="revoked"; item.revoked_at=datetime.now(UTC); item.revoked_by_administrator_id=actor.id; item.revocation_reason=reason; self._repository.save_permission(item)
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.AGENT_PERMISSION_REVOKED.value, resource_type="agent_permission", resource_id=item.id, details={"agent_id": str(agent_id), "permission_key": item.permission_key, "reason": reason})
            self._session.commit(); return item
        except Exception: self._session.rollback(); raise

    def exchange_credential(self, raw: str) -> IssuedAgentToken:
        try: public_id, _ = parse_agent_credential(raw)
        except InvalidAgentCredentialError as exc: raise InvalidAgentAuthenticationError from exc
        credential = self._repository.get_credential_by_public_id(public_id)
        if credential is None:
            # Equal-cost keyed comparison without revealing lookup state.
            try: verify_agent_credential(raw, "0" * 64, pepper=self._settings.agent_credential_pepper)
            except Exception: pass
            raise InvalidAgentAuthenticationError
        try: valid = verify_agent_credential(raw, credential.secret_hash, pepper=self._settings.agent_credential_pepper)
        except Exception as exc: raise InvalidAgentAuthenticationError from exc
        agent = self._repository.get_agent(company_id=credential.company_id, agent_id=credential.agent_id)
        company = self._companies.get_by_id(credential.company_id)
        now = datetime.now(UTC)
        if not valid or agent is None or agent.status != "active" or credential.status != "active" or (credential.expires_at and credential.expires_at <= now) or company is None or not company.is_active or company.status != CompanyStatus.ACTIVE.value: raise InvalidAgentAuthenticationError
        try:
            credential.last_used_at=now; self._repository.save_credential(credential)
            self._audit.append_agent_event(company_id=agent.company_id, actor_agent_id=agent.id, action=AuditAction.AGENT_AUTHENTICATED.value, resource_type="agent", resource_id=agent.id, details={"credential_id": str(credential.id)})
            token = create_agent_token(agent_id=agent.id, company_id=agent.company_id, credential_id=credential.id, auth_version=agent.auth_version, secret=self._settings.agent_jwt_secret, algorithm=self._settings.agent_jwt_algorithm, ttl_seconds=self._settings.agent_jwt_ttl_seconds, issuer=self._settings.agent_jwt_issuer, audience=self._settings.agent_jwt_audience)
            self._session.commit(); return IssuedAgentToken(token, self._settings.agent_jwt_ttl_seconds, agent, credential)
        except Exception: self._session.rollback(); raise

    def resolve_token(self, token: str) -> AuthenticatedAgent:
        try: claims: AgentTokenClaims = decode_agent_token(token, secret=self._settings.agent_jwt_secret, algorithm=self._settings.agent_jwt_algorithm, issuer=self._settings.agent_jwt_issuer, audience=self._settings.agent_jwt_audience)
        except InvalidAgentTokenError as exc: raise InvalidAgentAuthenticationError from exc
        agent = self._repository.get_agent(company_id=claims.company_id, agent_id=claims.agent_id)
        credential = self._repository.get_credential(company_id=claims.company_id, agent_id=claims.agent_id, credential_id=claims.credential_id)
        company = self._companies.get_by_id(claims.company_id); now = datetime.now(UTC)
        if agent is None or credential is None or agent.status != "active" or agent.auth_version != claims.auth_version or credential.status != "active" or (credential.expires_at and credential.expires_at <= now) or company is None or not company.is_active or company.status != CompanyStatus.ACTIVE.value: raise InvalidAgentAuthenticationError
        permissions = tuple(sorted(item.permission_key for item in self._repository.list_permissions(company_id=agent.company_id, agent_id=agent.id, active_only=True)))
        return AuthenticatedAgent(agent, credential, permissions)


def get_agent_identity_service(session: Annotated[Session, Depends(get_db_session)], settings: Annotated[Settings, Depends(get_settings)]) -> AgentIdentityService:
    return AgentIdentityService(AgentRepository(session), CompanyRepository(session), AuditLogService(AuditLogRepository(session)), session, settings)
