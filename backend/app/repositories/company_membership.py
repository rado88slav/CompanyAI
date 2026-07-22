"""Persistence operations for isolated company memberships."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.administrator import Administrator
from app.models.company import Company
from app.models.company_membership import CompanyMembership, CompanyRole


class CompanyMembershipRepository:
    """Access memberships with explicit company isolation."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, company_id: UUID, administrator_id: UUID, role: str) -> CompanyMembership:
        membership = CompanyMembership(company_id=company_id, administrator_id=administrator_id, role=role, is_active=True)
        self._session.add(membership)
        self._session.flush()
        self._session.refresh(membership)
        return membership

    def get(self, *, company_id: UUID, membership_id: UUID) -> CompanyMembership | None:
        statement = select(CompanyMembership).options(joinedload(CompanyMembership.administrator)).where(CompanyMembership.company_id == company_id, CompanyMembership.id == membership_id)
        return self._session.scalar(statement)

    def get_for_administrator(self, *, company_id: UUID, administrator_id: UUID) -> CompanyMembership | None:
        statement = select(CompanyMembership).where(CompanyMembership.company_id == company_id, CompanyMembership.administrator_id == administrator_id)
        return self._session.scalar(statement)

    def list(self, *, company_id: UUID, role: str | None, is_active: bool | None, limit: int, offset: int) -> list[CompanyMembership]:
        statement = select(CompanyMembership).options(joinedload(CompanyMembership.administrator)).where(CompanyMembership.company_id == company_id)
        statement = self._filters(statement, role=role, is_active=is_active)
        statement = statement.order_by(CompanyMembership.created_at.asc(), CompanyMembership.id.asc()).limit(limit).offset(offset)
        return list(self._session.scalars(statement).all())

    def count(self, *, company_id: UUID, role: str | None, is_active: bool | None) -> int:
        statement = select(func.count()).select_from(CompanyMembership).where(CompanyMembership.company_id == company_id)
        statement = self._filters(statement, role=role, is_active=is_active)
        return int(self._session.scalar(statement) or 0)

    @staticmethod
    def _filters(statement: object, *, role: str | None, is_active: bool | None):
        if role is not None:
            statement = statement.where(CompanyMembership.role == role)
        if is_active is not None:
            statement = statement.where(CompanyMembership.is_active == is_active)
        return statement

    def list_for_administrator(self, *, administrator_id: UUID, limit: int, offset: int) -> list[CompanyMembership]:
        statement = (select(CompanyMembership).join(Company, Company.id == CompanyMembership.company_id).options(joinedload(CompanyMembership.company)).where(CompanyMembership.administrator_id == administrator_id, CompanyMembership.is_active.is_(True), Company.is_active.is_(True)).order_by(CompanyMembership.created_at.asc(), CompanyMembership.id.asc()).limit(limit).offset(offset))
        return list(self._session.scalars(statement).all())

    def count_for_administrator(self, *, administrator_id: UUID) -> int:
        statement = select(func.count()).select_from(CompanyMembership).join(Company, Company.id == CompanyMembership.company_id).where(CompanyMembership.administrator_id == administrator_id, CompanyMembership.is_active.is_(True), Company.is_active.is_(True))
        return int(self._session.scalar(statement) or 0)

    def count_active_owners(self, *, company_id: UUID) -> int:
        statement = select(func.count()).select_from(CompanyMembership).where(CompanyMembership.company_id == company_id, CompanyMembership.role == CompanyRole.OWNER.value, CompanyMembership.is_active.is_(True))
        return int(self._session.scalar(statement) or 0)

    def lock_company(self, *, company_id: UUID) -> Company | None:
        return self._session.scalar(select(Company).where(Company.id == company_id).with_for_update())

    def set_role(self, membership: CompanyMembership, *, role: str) -> CompanyMembership:
        membership.role = role
        self._session.flush()
        self._session.refresh(membership)
        return membership

    def set_active(self, membership: CompanyMembership, *, is_active: bool) -> CompanyMembership:
        membership.is_active = is_active
        self._session.flush()
        self._session.refresh(membership)
        return membership
