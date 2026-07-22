"""Approval requests, immutable decisions, policies and usage ledger."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RequesterType(StrEnum):
    ADMINISTRATOR = "administrator"
    AGENT = "agent"
    SYSTEM = "system"


class ApprovalRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ApprovalDecisionValue(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"


class PolicyScope(StrEnum):
    PLATFORM = "platform"
    COMPANY = "company"


class PolicyEffect(StrEnum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    BLOCK = "block"


class PolicySourceType(StrEnum):
    APPROVAL_DECISION = "approval_decision"
    MANUAL = "manual"
    BOOTSTRAP = "bootstrap"
    SYSTEM_DEFAULT = "system_default"


class PolicySubjectType(StrEnum):
    ANY = "any"
    ADMINISTRATOR = "administrator"
    AGENT = "agent"


class AuthorizationPolicyStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    CONSUMED = "consumed"


class AuthorizationUsageStatus(StrEnum):
    RESERVED = "reserved"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RELEASED = "released"


MODES_SQL = "'ask_every_time','approve_single_action','approve_batch','approve_campaign','approve_until','allow_within_limits','always_require_approval','block'"


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        CheckConstraint("requester_type IN ('administrator','agent','system')", name="ck_approval_requests_requester_type"),
        CheckConstraint("(requester_type='administrator' AND requester_administrator_id IS NOT NULL AND requester_agent_id IS NULL) OR (requester_type='agent' AND requester_agent_id IS NOT NULL AND requester_administrator_id IS NULL) OR (requester_type='system' AND requester_administrator_id IS NULL AND requester_agent_id IS NULL)", name="ck_approval_requests_requester_identity"),
        CheckConstraint(f"authorization_mode IN ({MODES_SQL})", name="ck_approval_requests_mode"),
        CheckConstraint("risk_level IN ('low','medium','high','critical')", name="ck_approval_requests_risk"),
        CheckConstraint("status IN ('pending','approved','denied','cancelled','expired')", name="ck_approval_requests_status"),
        CheckConstraint("jsonb_typeof(requested_limits)='object'", name="ck_approval_requests_limits_object"),
        CheckConstraint("jsonb_typeof(requested_conditions)='object'", name="ck_approval_requests_conditions_object"),
        CheckConstraint("length(trim(action_type))>0 AND length(trim(scope_type))>0", name="ck_approval_requests_identifiers"),
        CheckConstraint("tool_identifier IS NULL OR length(trim(tool_identifier))>0", name="ck_approval_requests_tool"),
        CheckConstraint("decision_due_at IS NULL OR decision_due_at > created_at", name="ck_approval_requests_due_after_created"),
        Index("ix_approval_requests_company_status_created_id", "company_id", "status", "created_at", "id"),
        Index("ix_approval_requests_company_requester_admin_created_id", "company_id", "requester_administrator_id", "created_at", "id"),
        Index("ix_approval_requests_company_requester_agent_created_id", "company_id", "requester_agent_id", "created_at", "id"),
        Index("ix_approval_requests_company_action_status", "company_id", "action_type", "status"),
        Index("ix_approval_requests_company_campaign_status", "company_id", "campaign_id", "status"),
        Index("ix_approval_requests_company_risk_status", "company_id", "risk_level", "status"),
        Index("uq_approval_requests_pending_dedup", "company_id", "deduplication_key", unique=True, postgresql_where=text("status = 'pending'")),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    requester_type: Mapped[str] = mapped_column(String(20), nullable=False)
    requester_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    requester_agent_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("agents.id", ondelete="RESTRICT"))
    authorization_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_identifier: Mapped[str | None] = mapped_column(String(150))
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    target_resource_type: Mapped[str | None] = mapped_column(String(50))
    target_resource_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    campaign_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    batch_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    contact_list_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    provider_connection_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    requested_limits: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    requested_conditions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    reason: Mapped[str | None] = mapped_column(String(1000))
    deduplication_key: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"
    __table_args__ = (
        UniqueConstraint("approval_request_id", name="uq_approval_decisions_request"),
        CheckConstraint("decision IN ('approved','denied')", name="ck_approval_decisions_value"),
        CheckConstraint("jsonb_typeof(approved_limits)='object'", name="ck_approval_decisions_limits_object"),
        CheckConstraint("jsonb_typeof(approved_conditions)='object'", name="ck_approval_decisions_conditions_object"),
        Index("ix_approval_decisions_company_created_id", "company_id", "created_at", "id"),
        Index("ix_approval_decisions_request_created_id", "approval_request_id", "created_at", "id"),
        Index("ix_approval_decisions_company_approver_created_id", "company_id", "approver_administrator_id", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    approval_request_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("approval_requests.id", ondelete="RESTRICT"), nullable=False)
    approver_administrator_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    approved_mode: Mapped[str | None] = mapped_column(String(32))
    approved_limits: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    approved_conditions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    reason: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AuthorizationPolicy(Base):
    __tablename__ = "authorization_policies"
    __table_args__ = (
        CheckConstraint("policy_scope IN ('platform','company') AND ((policy_scope='platform' AND company_id IS NULL) OR (policy_scope='company' AND company_id IS NOT NULL))", name="ck_authorization_policies_scope"),
        CheckConstraint("effect IN ('allow','require_approval','block')", name="ck_authorization_policies_effect"),
        CheckConstraint(f"authorization_mode IN ({MODES_SQL})", name="ck_authorization_policies_mode"),
        CheckConstraint("source_type IN ('approval_decision','manual','bootstrap','system_default')", name="ck_authorization_policies_source"),
        CheckConstraint("(subject_type='any' AND subject_administrator_id IS NULL AND subject_agent_id IS NULL) OR (subject_type='administrator' AND subject_administrator_id IS NOT NULL AND subject_agent_id IS NULL) OR (subject_type='agent' AND subject_agent_id IS NOT NULL AND subject_administrator_id IS NULL)", name="ck_authorization_policies_subject"),
        CheckConstraint("status IN ('active','revoked','consumed')", name="ck_authorization_policies_status"),
        CheckConstraint("risk_level_max IS NULL OR risk_level_max IN ('low','medium','high','critical')", name="ck_authorization_policies_risk"),
        CheckConstraint("(max_total_actions IS NULL OR max_total_actions>0) AND (max_hourly_actions IS NULL OR max_hourly_actions>0) AND (max_daily_actions IS NULL OR max_daily_actions>0) AND (max_followups_per_target IS NULL OR max_followups_per_target>0)", name="ck_authorization_policies_positive_limits"),
        CheckConstraint("max_budget_amount IS NULL OR max_budget_amount>0", name="ck_authorization_policies_positive_budget"),
        CheckConstraint("(max_budget_amount IS NULL AND budget_currency IS NULL) OR (max_budget_amount IS NOT NULL AND budget_currency IS NOT NULL)", name="ck_authorization_policies_budget_currency"),
        CheckConstraint("expires_at IS NULL OR expires_at>valid_from", name="ck_authorization_policies_validity"),
        CheckConstraint("(status='revoked' AND revoked_at IS NOT NULL AND revoked_by_administrator_id IS NOT NULL) OR (status<>'revoked' AND revoked_at IS NULL AND revoked_by_administrator_id IS NULL)", name="ck_authorization_policies_revocation"),
        CheckConstraint("jsonb_typeof(conditions)='object' AND conditions_schema_version>0", name="ck_authorization_policies_conditions"),
        CheckConstraint("(effect='block' AND authorization_mode='block' AND max_total_actions IS NULL AND max_hourly_actions IS NULL AND max_daily_actions IS NULL AND max_followups_per_target IS NULL AND max_budget_amount IS NULL) OR (effect='require_approval' AND authorization_mode IN ('ask_every_time','always_require_approval')) OR (effect='allow' AND authorization_mode IN ('approve_single_action','approve_batch','approve_campaign','approve_until','allow_within_limits'))", name="ck_authorization_policies_effect_mode"),
        CheckConstraint("authorization_mode<>'allow_within_limits' OR max_total_actions IS NOT NULL OR max_hourly_actions IS NOT NULL OR max_daily_actions IS NOT NULL OR max_budget_amount IS NOT NULL OR expires_at IS NOT NULL", name="ck_authorization_policies_within_limits"),
        CheckConstraint("status<>'consumed' OR authorization_mode='approve_single_action'", name="ck_authorization_policies_consumed_single"),
        Index("ix_authorization_policies_company_status_effect_action", "company_id", "status", "effect", "action_type"),
        Index("ix_authorization_policies_company_tool_status", "company_id", "tool_identifier", "status"),
        Index("ix_authorization_policies_company_campaign_status", "company_id", "campaign_id", "status"),
        Index("ix_authorization_policies_company_subject_admin_status", "company_id", "subject_administrator_id", "status"),
        Index("ix_authorization_policies_company_subject_agent_status", "company_id", "subject_agent_id", "status"),
        Index("ix_authorization_policies_status_validity", "status", "valid_from", "expires_at"),
        Index("ix_authorization_policies_source_request", "source_approval_request_id"),
        Index("ix_authorization_policies_source_decision", "source_approval_decision_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    policy_scope: Mapped[str] = mapped_column(String(16), nullable=False)
    company_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"))
    effect: Mapped[str] = mapped_column(String(20), nullable=False)
    authorization_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
    source_approval_request_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("approval_requests.id", ondelete="RESTRICT"))
    source_approval_decision_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("approval_decisions.id", ondelete="RESTRICT"))
    created_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    subject_agent_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("agents.id", ondelete="RESTRICT"))
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    action_type: Mapped[str | None] = mapped_column(String(100))
    tool_identifier: Mapped[str | None] = mapped_column(String(150))
    campaign_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    batch_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    contact_list_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    provider_connection_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    risk_level_max: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    max_total_actions: Mapped[int | None] = mapped_column(Integer)
    max_hourly_actions: Mapped[int | None] = mapped_column(Integer)
    max_daily_actions: Mapped[int | None] = mapped_column(Integer)
    max_followups_per_target: Mapped[int | None] = mapped_column(Integer)
    max_budget_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    budget_currency: Mapped[str | None] = mapped_column(String(3))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    conditions_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    conditions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    revocation_reason: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AuthorizationUsage(Base):
    __tablename__ = "authorization_usages"
    __table_args__ = (
        UniqueConstraint("reservation_key", name="uq_authorization_usages_reservation_key"),
        CheckConstraint("(actor_type='administrator' AND actor_administrator_id IS NOT NULL AND actor_agent_id IS NULL) OR (actor_type='agent' AND actor_agent_id IS NOT NULL AND actor_administrator_id IS NULL) OR (actor_type='system' AND actor_administrator_id IS NULL AND actor_agent_id IS NULL)", name="ck_authorization_usages_actor"),
        CheckConstraint("quantity>0 AND reserved_budget_amount>=0", name="ck_authorization_usages_amounts"),
        CheckConstraint("(reserved_budget_amount=0 AND budget_currency IS NULL) OR (reserved_budget_amount>0 AND budget_currency IS NOT NULL)", name="ck_authorization_usages_budget_currency"),
        CheckConstraint("followup_index IS NULL OR followup_index>=0", name="ck_authorization_usages_followup"),
        CheckConstraint("status IN ('reserved','succeeded','failed','released')", name="ck_authorization_usages_status"),
        CheckConstraint("reservation_expires_at>reserved_at", name="ck_authorization_usages_reservation_expiry"),
        CheckConstraint("(status='reserved' AND finalized_at IS NULL AND released_at IS NULL) OR (status IN ('succeeded','failed') AND finalized_at IS NOT NULL AND released_at IS NULL) OR (status='released' AND released_at IS NOT NULL)", name="ck_authorization_usages_lifecycle"),
        Index("uq_authorization_usages_execution", "execution_id", unique=True, postgresql_where=text("execution_id IS NOT NULL")),
        Index("ix_authorization_usages_policy_status_reserved", "authorization_policy_id", "status", "reserved_at"),
        Index("ix_authorization_usages_company_campaign_status_reserved", "company_id", "campaign_id", "status", "reserved_at"),
        Index("ix_authorization_usages_company_action_status_reserved", "company_id", "action_type", "status", "reserved_at"),
        Index("ix_authorization_usages_expiry_status", "reservation_expires_at", "status"),
        Index("ix_authorization_usages_company_target", "company_id", "target_resource_type", "target_resource_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    authorization_policy_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("authorization_policies.id", ondelete="RESTRICT"), nullable=False)
    reservation_key: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    execution_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    actor_agent_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("agents.id", ondelete="RESTRICT"))
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_identifier: Mapped[str | None] = mapped_column(String(150))
    campaign_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    batch_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    target_resource_type: Mapped[str | None] = mapped_column(String(50))
    target_resource_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    followup_index: Mapped[int | None] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    reserved_budget_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=0, server_default="0")
    budget_currency: Mapped[str | None] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="reserved", server_default="reserved")
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reservation_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
