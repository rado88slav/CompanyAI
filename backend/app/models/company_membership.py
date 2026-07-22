"""Company membership database model."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CompanyRole(StrEnum):
    """Supported company-scoped roles."""

    OWNER = "owner"
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class CompanyMembership(Base):
    """An administrator's role in exactly one company."""

    __tablename__ = "company_memberships"
    __table_args__ = (
        UniqueConstraint("company_id", "administrator_id", name="uq_company_memberships_company_administrator"),
        CheckConstraint("role IN ('owner', 'admin', 'operator', 'viewer')", name="ck_company_memberships_role"),
        Index("ix_company_memberships_administrator_active_company", "administrator_id", "is_active", "company_id"),
        Index("ix_company_memberships_company_active_role", "company_id", "is_active", "role"),
        Index("ix_company_memberships_company_created_id", "company_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    administrator_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    administrator: Mapped["Administrator"] = relationship()  # noqa: F821
    company: Mapped["Company"] = relationship()  # noqa: F821
