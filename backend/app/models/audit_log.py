"""Append-only audit log database model."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditScope(StrEnum):
    """Supported audit event scopes."""

    COMPANY = "company"
    PLATFORM = "platform"


class AuditActorType(StrEnum):
    """Supported audit event actor types."""

    ADMINISTRATOR = "administrator"
    SYSTEM = "system"


class AuditAction(StrEnum):
    """Normalized audit actions created in the current phase."""

    COMPANY_CREATED = "company.created"
    COMPANY_UPDATED = "company.updated"
    COMPANY_ACTIVATED = "company.activated"
    COMPANY_DEACTIVATED = "company.deactivated"
    COMPANY_MEMBERSHIP_CREATED = "company_membership.created"
    COMPANY_MEMBERSHIP_ROLE_CHANGED = "company_membership.role_changed"
    COMPANY_MEMBERSHIP_ACTIVATED = "company_membership.activated"
    COMPANY_MEMBERSHIP_DEACTIVATED = "company_membership.deactivated"
    APPROVAL_REQUEST_CREATED = "approval_request.created"
    APPROVAL_REQUEST_CANCELLED = "approval_request.cancelled"
    APPROVAL_REQUEST_EXPIRED = "approval_request.expired"
    APPROVAL_REQUEST_APPROVED = "approval_request.approved"
    APPROVAL_REQUEST_DENIED = "approval_request.denied"
    AUTHORIZATION_POLICY_CREATED = "authorization_policy.created"
    AUTHORIZATION_POLICY_REVOKED = "authorization_policy.revoked"
    AUTHORIZATION_USAGE_RESERVED = "authorization_usage.reserved"
    AUTHORIZATION_USAGE_SUCCEEDED = "authorization_usage.succeeded"
    AUTHORIZATION_USAGE_FAILED = "authorization_usage.failed"
    AUTHORIZATION_USAGE_RELEASED = "authorization_usage.released"


class AuditLog(Base):
    """An immutable application audit event."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('company', 'platform')",
            name="ck_audit_logs_scope",
        ),
        CheckConstraint(
            "actor_type IN ('administrator', 'system')",
            name="ck_audit_logs_actor_type",
        ),
        CheckConstraint(
            "(scope = 'company' AND company_id IS NOT NULL) OR "
            "(scope = 'platform' AND company_id IS NULL)",
            name="ck_audit_logs_scope_company",
        ),
        CheckConstraint(
            "(actor_type = 'administrator' AND "
            "actor_administrator_id IS NOT NULL) OR "
            "(actor_type = 'system' AND "
            "actor_administrator_id IS NULL)",
            name="ck_audit_logs_actor_administrator",
        ),
        CheckConstraint(
            "length(trim(action)) > 0",
            name="ck_audit_logs_action_not_empty",
        ),
        CheckConstraint(
            "length(trim(resource_type)) > 0",
            name="ck_audit_logs_resource_type_not_empty",
        ),
        CheckConstraint(
            "jsonb_typeof(details) = 'object'",
            name="ck_audit_logs_details_object",
        ),
        Index(
            "ix_audit_logs_company_created_id",
            "company_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_audit_logs_actor_created_id",
            "actor_administrator_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_audit_logs_action_created_id",
            "action",
            "created_at",
            "id",
        ),
        Index(
            "ix_audit_logs_resource_created_id",
            "resource_type",
            "resource_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    company_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=True,
    )
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_administrator_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("administrators.id", ondelete="RESTRICT"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
