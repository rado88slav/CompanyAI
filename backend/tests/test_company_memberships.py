"""Focused tests for company memberships, roles and invariants."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.dependencies.company_authorization import (
    require_company_settings_read,
    require_company_settings_write,
    require_memberships_read,
)
from app.core.company_permissions import CompanyPermission, role_has_permission
from app.models.company_membership import CompanyMembership, CompanyRole
from app.schemas.company_context import ActiveCompanyContext
from app.services.company_membership import CompanyMembershipService, InactiveAdministratorError, LastActiveOwnerError, MembershipAuthorizationError, MembershipConflictError


class Session:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
    def commit(self) -> None: self.commits += 1
    def rollback(self) -> None: self.rollbacks += 1


class Memberships:
    def __init__(self, target=None, *, owners: int = 1) -> None:
        self.target = target
        self.owners = owners
        self.locked = False
    def get(self, *, company_id, membership_id):
        return self.target if self.target and self.target.company_id == company_id and self.target.id == membership_id else None
    def get_for_administrator(self, *, company_id, administrator_id): return self.target if self.target and self.target.company_id == company_id and self.target.administrator_id == administrator_id else None
    def lock_company(self, *, company_id): self.locked = True; return SimpleNamespace(id=company_id)
    def count_active_owners(self, *, company_id): return self.owners
    def create(self, *, company_id, administrator_id, role):
        self.target = SimpleNamespace(id=uuid4(), company_id=company_id, administrator_id=administrator_id, role=role, is_active=True)
        return self.target
    def set_role(self, membership, *, role): membership.role = role; return membership
    def set_active(self, membership, *, is_active): membership.is_active = is_active; return membership
    def list(self, **kwargs): return []
    def count(self, **kwargs): return 0
    def list_for_administrator(self, **kwargs): return []
    def count_for_administrator(self, **kwargs): return 0


class Audit:
    def __init__(self, *, fail: bool = False) -> None: self.events = []; self.fail = fail
    def append_company_event(self, **event):
        if self.fail: raise RuntimeError("audit failed")
        self.events.append(event)


def admin(*, role=None, superuser=False, active=True):
    actor = SimpleNamespace(id=uuid4(), is_superuser=superuser, is_active=active)
    membership = None if role is None else SimpleNamespace(administrator_id=actor.id, role=role, is_active=True)
    return actor, membership


def target(company_id, administrator_id=None, *, role="viewer", active=True):
    return SimpleNamespace(id=uuid4(), company_id=company_id, administrator_id=administrator_id or uuid4(), role=role, is_active=active)


def service(repository, *, administrator=None, audit=None):
    session = Session()
    administrators = SimpleNamespace(get_by_id=lambda _id: administrator or SimpleNamespace(id=_id, is_active=True))
    companies = SimpleNamespace(get_by_id=lambda company_id: SimpleNamespace(id=company_id))
    audit = audit or Audit()
    return CompanyMembershipService(repository, companies, administrators, audit, session), session, audit


@pytest.mark.parametrize("role", list(CompanyRole))
def test_every_role_can_read_settings_and_activity(role: CompanyRole) -> None:
    assert role_has_permission(role.value, CompanyPermission.SETTINGS_READ)
    assert role_has_permission(role.value, CompanyPermission.ACTIVITY_READ)


@pytest.mark.parametrize("role,allowed", [(CompanyRole.OWNER, True), (CompanyRole.ADMIN, True), (CompanyRole.OPERATOR, False), (CompanyRole.VIEWER, False)])
def test_settings_write_matrix(role: CompanyRole, allowed: bool) -> None:
    assert role_has_permission(role.value, CompanyPermission.SETTINGS_WRITE) is allowed


def typed_context(*, role: str | None, superuser: bool = False) -> ActiveCompanyContext:
    """Build a complete request context for dependency regression tests."""

    administrator = SimpleNamespace(
        id=uuid4(),
        is_active=True,
        is_superuser=superuser,
    )
    membership = None
    if role is not None:
        membership = SimpleNamespace(
            administrator_id=administrator.id,
            role=role,
            is_active=True,
        )
    return ActiveCompanyContext(
        administrator=administrator,  # type: ignore[arg-type]
        company=SimpleNamespace(id=uuid4()),  # type: ignore[arg-type]
        membership=membership,  # type: ignore[arg-type]
        is_platform_superuser=superuser,
    )


def test_authorization_dependencies_accept_typed_allowed_contexts() -> None:
    owner_context = typed_context(role=CompanyRole.OWNER.value)
    viewer_context = typed_context(role=CompanyRole.VIEWER.value)
    superuser_context = typed_context(role=None, superuser=True)

    assert require_company_settings_write(owner_context) is owner_context
    assert require_company_settings_read(viewer_context) is viewer_context
    assert require_memberships_read(superuser_context) is superuser_context


@pytest.mark.parametrize(
    ("dependency", "role"),
    [
        (require_company_settings_write, CompanyRole.OPERATOR.value),
        (require_memberships_read, CompanyRole.VIEWER.value),
        (require_company_settings_read, None),
    ],
)
def test_authorization_dependencies_reject_insufficient_roles(
    dependency,
    role: str | None,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        dependency(typed_context(role=role))

    assert exc_info.value.status_code == 403


def test_model_contains_required_constraints_and_indexes() -> None:
    table = CompanyMembership.__table__
    assert {column.name for column in table.columns} == {"id", "company_id", "administrator_id", "role", "is_active", "created_at", "updated_at"}
    assert {index.name for index in table.indexes} == {"ix_company_memberships_administrator_active_company", "ix_company_memberships_company_active_role", "ix_company_memberships_company_created_id"}
    assert any(constraint.name == "uq_company_memberships_company_administrator" for constraint in table.constraints)


def test_admin_can_create_operator_but_not_admin() -> None:
    company_id = uuid4(); actor, actor_membership = admin(role="admin")
    repository = Memberships(owners=1); member_service, session, audit = service(repository)
    created = member_service.create_membership(company_id=company_id, administrator_id=uuid4(), role="operator", actor=actor, actor_membership=actor_membership)
    assert created.role == "operator" and session.commits == 1
    assert audit.events[0]["action"] == "company_membership.created"
    with pytest.raises(MembershipAuthorizationError):
        member_service.create_membership(company_id=company_id, administrator_id=uuid4(), role="admin", actor=actor, actor_membership=actor_membership)


def test_first_owner_requires_platform_superuser_and_owner_role() -> None:
    repository = Memberships(owners=0); member_service, _, _ = service(repository)
    actor, owner_membership = admin(role="owner")
    with pytest.raises(MembershipAuthorizationError):
        member_service.create_membership(company_id=uuid4(), administrator_id=uuid4(), role="owner", actor=actor, actor_membership=owner_membership)
    superuser, _ = admin(superuser=True)
    with pytest.raises(MembershipAuthorizationError):
        member_service.create_membership(company_id=uuid4(), administrator_id=uuid4(), role="viewer", actor=superuser, actor_membership=None)


def test_last_active_owner_is_locked_and_protected() -> None:
    company_id = uuid4(); owner = target(company_id, role="owner")
    repository = Memberships(owner, owners=1); member_service, _, _ = service(repository)
    actor, _ = admin(superuser=True)
    with pytest.raises(LastActiveOwnerError):
        member_service.set_active(company_id=company_id, membership_id=owner.id, is_active=False, actor=actor, actor_membership=None)
    assert repository.locked is True


def test_owner_self_change_allowed_only_when_another_owner_remains() -> None:
    company_id = uuid4(); actor, actor_membership = admin(role="owner")
    owner = target(company_id, actor.id, role="owner")
    repository = Memberships(owner, owners=2); member_service, session, _ = service(repository)
    changed = member_service.change_role(company_id=company_id, membership_id=owner.id, role="viewer", actor=actor, actor_membership=actor_membership)
    assert changed.role == "viewer" and session.commits == 1 and repository.locked


def test_admin_cannot_modify_self() -> None:
    company_id = uuid4(); actor, actor_membership = admin(role="admin")
    own = target(company_id, actor.id, role="admin")
    member_service, _, _ = service(Memberships(own))
    with pytest.raises(MembershipAuthorizationError):
        member_service.set_active(company_id=company_id, membership_id=own.id, is_active=False, actor=actor, actor_membership=actor_membership)


def test_inactive_administrator_cannot_receive_membership() -> None:
    actor, _ = admin(superuser=True); company_id = uuid4()
    member_service, _, _ = service(Memberships(owners=1), administrator=SimpleNamespace(is_active=False))
    with pytest.raises(InactiveAdministratorError):
        member_service.create_membership(company_id=company_id, administrator_id=uuid4(), role="viewer", actor=actor, actor_membership=None)


def test_duplicate_membership_is_a_conflict() -> None:
    actor, _ = admin(superuser=True); company_id = uuid4(); existing = target(company_id)
    member_service, _, _ = service(Memberships(existing))
    with pytest.raises(MembershipConflictError):
        member_service.create_membership(company_id=company_id, administrator_id=existing.administrator_id, role="viewer", actor=actor, actor_membership=None)


def test_noop_lifecycle_is_audited_with_changed_false() -> None:
    company_id = uuid4(); existing = target(company_id, active=True)
    actor, _ = admin(superuser=True); member_service, session, audit = service(Memberships(existing))
    member_service.set_active(company_id=company_id, membership_id=existing.id, is_active=True, actor=actor, actor_membership=None)
    assert session.commits == 1
    assert audit.events[0]["details"]["changed"] is False


def test_audit_failure_rolls_back_membership_transaction() -> None:
    actor, _ = admin(superuser=True); repository = Memberships(owners=1)
    member_service, session, _ = service(repository, audit=Audit(fail=True))
    with pytest.raises(RuntimeError, match="audit failed"):
        member_service.create_membership(company_id=uuid4(), administrator_id=uuid4(), role="viewer", actor=actor, actor_membership=None)
    assert session.commits == 0 and session.rollbacks == 1
