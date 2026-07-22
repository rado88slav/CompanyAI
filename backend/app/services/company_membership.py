"""Business service for company memberships and role invariants."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.administrator import Administrator
from app.models.audit_log import AuditAction
from app.models.company_membership import CompanyMembership, CompanyRole
from app.repositories.administrator import AdministratorRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.company import CompanyRepository
from app.repositories.company_membership import CompanyMembershipRepository
from app.services.audit_log import AuditLogService
from app.services.company import CompanyNotFoundError


class MembershipNotFoundError(Exception): pass
class MembershipConflictError(Exception): pass
class MembershipAuthorizationError(Exception): pass
class InactiveAdministratorError(Exception): pass
class LastActiveOwnerError(Exception): pass


class CompanyMembershipService:
    """Coordinate membership authorization, persistence and auditing."""

    def __init__(self, repository: CompanyMembershipRepository, company_repository: CompanyRepository, administrator_repository: AdministratorRepository, audit_service: AuditLogService, session: Session) -> None:
        self._repository = repository
        self._company_repository = company_repository
        self._administrator_repository = administrator_repository
        self._audit_service = audit_service
        self._session = session

    def get_active_for_administrator(self, *, company_id: UUID, administrator_id: UUID) -> CompanyMembership | None:
        membership = self._repository.get_for_administrator(company_id=company_id, administrator_id=administrator_id)
        return membership if membership is not None and membership.is_active else None

    def get_membership(self, *, company_id: UUID, membership_id: UUID) -> CompanyMembership:
        membership = self._repository.get(company_id=company_id, membership_id=membership_id)
        if membership is None:
            raise MembershipNotFoundError
        return membership

    def list_memberships(self, *, company_id: UUID, role: str | None, is_active: bool | None, limit: int, offset: int) -> tuple[list[CompanyMembership], int]:
        return (self._repository.list(company_id=company_id, role=role, is_active=is_active, limit=limit, offset=offset), self._repository.count(company_id=company_id, role=role, is_active=is_active))

    def list_my_memberships(self, *, administrator_id: UUID, limit: int, offset: int) -> tuple[list[CompanyMembership], int]:
        return (self._repository.list_for_administrator(administrator_id=administrator_id, limit=limit, offset=offset), self._repository.count_for_administrator(administrator_id=administrator_id))

    @staticmethod
    def _may_manage_role(*, actor: Administrator, actor_membership: CompanyMembership | None, role: str) -> bool:
        if actor.is_superuser or (actor_membership and actor_membership.role == CompanyRole.OWNER.value):
            return True
        return bool(actor_membership and actor_membership.role == CompanyRole.ADMIN.value and role in {CompanyRole.OPERATOR.value, CompanyRole.VIEWER.value})

    def _require_target_permission(self, *, actor: Administrator, actor_membership: CompanyMembership | None, target: CompanyMembership | None, new_role: str | None = None) -> None:
        roles = [role for role in (target.role if target else None, new_role) if role]
        if not all(self._may_manage_role(actor=actor, actor_membership=actor_membership, role=role) for role in roles):
            raise MembershipAuthorizationError
        if target is not None and target.administrator_id == actor.id:
            if actor_membership and actor_membership.role == CompanyRole.ADMIN.value:
                raise MembershipAuthorizationError

    def _require_owner_survives(self, *, company_id: UUID, target: CompanyMembership) -> None:
        if target.role != CompanyRole.OWNER.value or not target.is_active:
            return
        if self._repository.lock_company(company_id=company_id) is None:
            raise CompanyNotFoundError
        if self._repository.count_active_owners(company_id=company_id) <= 1:
            raise LastActiveOwnerError

    def create_membership(self, *, company_id: UUID, administrator_id: UUID, role: str, actor: Administrator, actor_membership: CompanyMembership | None) -> CompanyMembership:
        self._require_target_permission(actor=actor, actor_membership=actor_membership, target=None, new_role=role)
        if self._company_repository.get_by_id(company_id) is None:
            raise CompanyNotFoundError
        administrator = self._administrator_repository.get_by_id(administrator_id)
        if administrator is None:
            raise MembershipNotFoundError
        if not administrator.is_active:
            raise InactiveAdministratorError
        if self._repository.get_for_administrator(company_id=company_id, administrator_id=administrator_id) is not None:
            raise MembershipConflictError
        self._repository.lock_company(company_id=company_id)
        owner_count = self._repository.count_active_owners(company_id=company_id)
        if owner_count == 0 and (not actor.is_superuser or role != CompanyRole.OWNER.value):
            raise MembershipAuthorizationError
        try:
            membership = self._repository.create(company_id=company_id, administrator_id=administrator_id, role=role)
            self._audit_service.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.COMPANY_MEMBERSHIP_CREATED.value, resource_type="company_membership", resource_id=membership.id, details={"administrator_id": str(administrator_id), "role": role, "is_active": True})
            self._session.commit()
            return membership
        except IntegrityError as exc:
            self._session.rollback()
            raise MembershipConflictError from exc
        except Exception:
            self._session.rollback()
            raise

    def change_role(self, *, company_id: UUID, membership_id: UUID, role: str, actor: Administrator, actor_membership: CompanyMembership | None) -> CompanyMembership:
        target = self.get_membership(company_id=company_id, membership_id=membership_id)
        self._require_target_permission(actor=actor, actor_membership=actor_membership, target=target, new_role=role)
        if target.role == CompanyRole.OWNER.value and role != CompanyRole.OWNER.value:
            self._require_owner_survives(company_id=company_id, target=target)
        previous = target.role
        try:
            updated = self._repository.set_role(target, role=role)
            self._audit_service.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.COMPANY_MEMBERSHIP_ROLE_CHANGED.value, resource_type="company_membership", resource_id=target.id, details={"administrator_id": str(target.administrator_id), "previous_role": previous, "new_role": role, "changed": previous != role})
            self._session.commit()
            return updated
        except Exception:
            self._session.rollback(); raise

    def set_active(self, *, company_id: UUID, membership_id: UUID, is_active: bool, actor: Administrator, actor_membership: CompanyMembership | None) -> CompanyMembership:
        target = self.get_membership(company_id=company_id, membership_id=membership_id)
        self._require_target_permission(actor=actor, actor_membership=actor_membership, target=target)
        if not is_active:
            self._require_owner_survives(company_id=company_id, target=target)
        if is_active:
            administrator = self._administrator_repository.get_by_id(target.administrator_id)
            if administrator is None:
                raise MembershipNotFoundError
            if not administrator.is_active:
                raise InactiveAdministratorError
        previous = target.is_active
        action = AuditAction.COMPANY_MEMBERSHIP_ACTIVATED if is_active else AuditAction.COMPANY_MEMBERSHIP_DEACTIVATED
        try:
            updated = self._repository.set_active(target, is_active=is_active)
            self._audit_service.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=action.value, resource_type="company_membership", resource_id=target.id, details={"administrator_id": str(target.administrator_id), "previous_is_active": previous, "new_is_active": is_active, "changed": previous != is_active})
            self._session.commit()
            return updated
        except Exception:
            self._session.rollback(); raise


def get_company_membership_service(session: Annotated[Session, Depends(get_db_session)]) -> CompanyMembershipService:
    return CompanyMembershipService(CompanyMembershipRepository(session), CompanyRepository(session), AdministratorRepository(session), AuditLogService(AuditLogRepository(session)), session)
