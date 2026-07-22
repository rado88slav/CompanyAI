"""Create Approval Manager and authorization policy tables.

Revision ID: 0007_approval_manager
Revises: 0006_company_memberships
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_approval_manager"
down_revision: str | None = "0006_company_memberships"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MODES_SQL = "'ask_every_time','approve_single_action','approve_batch','approve_campaign','approve_until','allow_within_limits','always_require_approval','block'"


def upgrade() -> None:
    """Create the schema only; no policies or local identifiers are inserted."""

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("requester_type", sa.String(length=20), nullable=False),
        sa.Column("requester_administrator_id", sa.Uuid(), nullable=True),
        sa.Column("requester_agent_id", sa.Uuid(), nullable=True),
        sa.Column("authorization_mode", sa.String(length=32), nullable=False),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column("tool_identifier", sa.String(length=150), nullable=True),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=True),
        sa.Column("target_resource_type", sa.String(length=50), nullable=True),
        sa.Column("target_resource_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("contact_list_id", sa.Uuid(), nullable=True),
        sa.Column("provider_connection_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("requested_limits", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("requested_conditions", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column("deduplication_key", sa.String(length=64), nullable=False),
        sa.Column("decision_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("requester_type IN ('administrator','agent','system')", name="ck_approval_requests_requester_type"),
        sa.CheckConstraint("(requester_type='administrator' AND requester_administrator_id IS NOT NULL AND requester_agent_id IS NULL) OR (requester_type='agent' AND requester_agent_id IS NOT NULL AND requester_administrator_id IS NULL) OR (requester_type='system' AND requester_administrator_id IS NULL AND requester_agent_id IS NULL)", name="ck_approval_requests_requester_identity"),
        sa.CheckConstraint(f"authorization_mode IN ({MODES_SQL})", name="ck_approval_requests_mode"),
        sa.CheckConstraint("risk_level IN ('low','medium','high','critical')", name="ck_approval_requests_risk"),
        sa.CheckConstraint("status IN ('pending','approved','denied','cancelled','expired')", name="ck_approval_requests_status"),
        sa.CheckConstraint("jsonb_typeof(requested_limits)='object'", name="ck_approval_requests_limits_object"),
        sa.CheckConstraint("jsonb_typeof(requested_conditions)='object'", name="ck_approval_requests_conditions_object"),
        sa.CheckConstraint("length(trim(action_type))>0 AND length(trim(scope_type))>0", name="ck_approval_requests_identifiers"),
        sa.CheckConstraint("tool_identifier IS NULL OR length(trim(tool_identifier))>0", name="ck_approval_requests_tool"),
        sa.CheckConstraint("decision_due_at IS NULL OR decision_due_at > created_at", name="ck_approval_requests_due_after_created"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_approval_requests_company_id_companies", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requester_administrator_id"], ["administrators.id"], name="fk_approval_requests_requester_administrator_id_administrators", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_requests_company_status_created_id", "approval_requests", ["company_id", "status", "created_at", "id"])
    op.create_index("ix_approval_requests_company_requester_admin_created_id", "approval_requests", ["company_id", "requester_administrator_id", "created_at", "id"])
    op.create_index("ix_approval_requests_company_requester_agent_created_id", "approval_requests", ["company_id", "requester_agent_id", "created_at", "id"])
    op.create_index("ix_approval_requests_company_action_status", "approval_requests", ["company_id", "action_type", "status"])
    op.create_index("ix_approval_requests_company_campaign_status", "approval_requests", ["company_id", "campaign_id", "status"])
    op.create_index("ix_approval_requests_company_risk_status", "approval_requests", ["company_id", "risk_level", "status"])
    op.create_index("uq_approval_requests_pending_dedup", "approval_requests", ["company_id", "deduplication_key"], unique=True, postgresql_where=sa.text("status = 'pending'"))

    op.create_table(
        "approval_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("approval_request_id", sa.Uuid(), nullable=False),
        sa.Column("approver_administrator_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("approved_mode", sa.String(length=32), nullable=True),
        sa.Column("approved_limits", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("approved_conditions", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("decision IN ('approved','denied')", name="ck_approval_decisions_value"),
        sa.CheckConstraint("jsonb_typeof(approved_limits)='object'", name="ck_approval_decisions_limits_object"),
        sa.CheckConstraint("jsonb_typeof(approved_conditions)='object'", name="ck_approval_decisions_conditions_object"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_approval_decisions_company_id_companies", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approval_requests.id"], name="fk_approval_decisions_approval_request_id_approval_requests", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approver_administrator_id"], ["administrators.id"], name="fk_approval_decisions_approver_administrator_id_administrators", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("approval_request_id", name="uq_approval_decisions_request"),
    )
    op.create_index("ix_approval_decisions_company_created_id", "approval_decisions", ["company_id", "created_at", "id"])
    op.create_index("ix_approval_decisions_request_created_id", "approval_decisions", ["approval_request_id", "created_at", "id"])
    op.create_index("ix_approval_decisions_company_approver_created_id", "approval_decisions", ["company_id", "approver_administrator_id", "created_at", "id"])

    op.create_table(
        "authorization_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("policy_scope", sa.String(length=16), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("effect", sa.String(length=20), nullable=False),
        sa.Column("authorization_mode", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=24), nullable=False),
        sa.Column("source_approval_request_id", sa.Uuid(), nullable=True),
        sa.Column("source_approval_decision_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_administrator_id", sa.Uuid(), nullable=True),
        sa.Column("subject_type", sa.String(length=20), nullable=False),
        sa.Column("subject_administrator_id", sa.Uuid(), nullable=True),
        sa.Column("subject_agent_id", sa.Uuid(), nullable=True),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=True),
        sa.Column("action_type", sa.String(length=100), nullable=True),
        sa.Column("tool_identifier", sa.String(length=150), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("contact_list_id", sa.Uuid(), nullable=True),
        sa.Column("provider_connection_id", sa.Uuid(), nullable=True),
        sa.Column("risk_level_max", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("max_total_actions", sa.Integer(), nullable=True),
        sa.Column("max_hourly_actions", sa.Integer(), nullable=True),
        sa.Column("max_daily_actions", sa.Integer(), nullable=True),
        sa.Column("max_followups_per_target", sa.Integer(), nullable=True),
        sa.Column("max_budget_amount", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("budget_currency", sa.String(length=3), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("conditions_schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("conditions", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_administrator_id", sa.Uuid(), nullable=True),
        sa.Column("revocation_reason", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("policy_scope IN ('platform','company') AND ((policy_scope='platform' AND company_id IS NULL) OR (policy_scope='company' AND company_id IS NOT NULL))", name="ck_authorization_policies_scope"),
        sa.CheckConstraint("effect IN ('allow','require_approval','block')", name="ck_authorization_policies_effect"),
        sa.CheckConstraint(f"authorization_mode IN ({MODES_SQL})", name="ck_authorization_policies_mode"),
        sa.CheckConstraint("source_type IN ('approval_decision','manual','bootstrap','system_default')", name="ck_authorization_policies_source"),
        sa.CheckConstraint("(subject_type='any' AND subject_administrator_id IS NULL AND subject_agent_id IS NULL) OR (subject_type='administrator' AND subject_administrator_id IS NOT NULL AND subject_agent_id IS NULL) OR (subject_type='agent' AND subject_agent_id IS NOT NULL AND subject_administrator_id IS NULL)", name="ck_authorization_policies_subject"),
        sa.CheckConstraint("status IN ('active','revoked','consumed')", name="ck_authorization_policies_status"),
        sa.CheckConstraint("risk_level_max IS NULL OR risk_level_max IN ('low','medium','high','critical')", name="ck_authorization_policies_risk"),
        sa.CheckConstraint("(max_total_actions IS NULL OR max_total_actions>0) AND (max_hourly_actions IS NULL OR max_hourly_actions>0) AND (max_daily_actions IS NULL OR max_daily_actions>0) AND (max_followups_per_target IS NULL OR max_followups_per_target>0)", name="ck_authorization_policies_positive_limits"),
        sa.CheckConstraint("max_budget_amount IS NULL OR max_budget_amount>0", name="ck_authorization_policies_positive_budget"),
        sa.CheckConstraint("(max_budget_amount IS NULL AND budget_currency IS NULL) OR (max_budget_amount IS NOT NULL AND budget_currency IS NOT NULL)", name="ck_authorization_policies_budget_currency"),
        sa.CheckConstraint("expires_at IS NULL OR expires_at>valid_from", name="ck_authorization_policies_validity"),
        sa.CheckConstraint("(status='revoked' AND revoked_at IS NOT NULL AND revoked_by_administrator_id IS NOT NULL) OR (status<>'revoked' AND revoked_at IS NULL AND revoked_by_administrator_id IS NULL)", name="ck_authorization_policies_revocation"),
        sa.CheckConstraint("jsonb_typeof(conditions)='object' AND conditions_schema_version>0", name="ck_authorization_policies_conditions"),
        sa.CheckConstraint("(effect='block' AND authorization_mode='block' AND max_total_actions IS NULL AND max_hourly_actions IS NULL AND max_daily_actions IS NULL AND max_followups_per_target IS NULL AND max_budget_amount IS NULL) OR (effect='require_approval' AND authorization_mode IN ('ask_every_time','always_require_approval')) OR (effect='allow' AND authorization_mode IN ('approve_single_action','approve_batch','approve_campaign','approve_until','allow_within_limits'))", name="ck_authorization_policies_effect_mode"),
        sa.CheckConstraint("authorization_mode<>'allow_within_limits' OR max_total_actions IS NOT NULL OR max_hourly_actions IS NOT NULL OR max_daily_actions IS NOT NULL OR max_budget_amount IS NOT NULL OR expires_at IS NOT NULL", name="ck_authorization_policies_within_limits"),
        sa.CheckConstraint("status<>'consumed' OR authorization_mode='approve_single_action'", name="ck_authorization_policies_consumed_single"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_authorization_policies_company_id_companies", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_approval_request_id"], ["approval_requests.id"], name="fk_auth_policies_source_request", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_approval_decision_id"], ["approval_decisions.id"], name="fk_auth_policies_source_decision", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_administrator_id"], ["administrators.id"], name="fk_auth_policies_created_by_admin", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subject_administrator_id"], ["administrators.id"], name="fk_auth_policies_subject_admin", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by_administrator_id"], ["administrators.id"], name="fk_auth_policies_revoked_by_admin", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_authorization_policies_company_status_effect_action", "authorization_policies", ["company_id", "status", "effect", "action_type"])
    op.create_index("ix_authorization_policies_company_tool_status", "authorization_policies", ["company_id", "tool_identifier", "status"])
    op.create_index("ix_authorization_policies_company_campaign_status", "authorization_policies", ["company_id", "campaign_id", "status"])
    op.create_index("ix_authorization_policies_company_subject_admin_status", "authorization_policies", ["company_id", "subject_administrator_id", "status"])
    op.create_index("ix_authorization_policies_company_subject_agent_status", "authorization_policies", ["company_id", "subject_agent_id", "status"])
    op.create_index("ix_authorization_policies_status_validity", "authorization_policies", ["status", "valid_from", "expires_at"])
    op.create_index("ix_authorization_policies_source_request", "authorization_policies", ["source_approval_request_id"])
    op.create_index("ix_authorization_policies_source_decision", "authorization_policies", ["source_approval_decision_id"])

    op.create_table(
        "authorization_usages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("authorization_policy_id", sa.Uuid(), nullable=False),
        sa.Column("reservation_key", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_administrator_id", sa.Uuid(), nullable=True),
        sa.Column("actor_agent_id", sa.Uuid(), nullable=True),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column("tool_identifier", sa.String(length=150), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("target_resource_type", sa.String(length=50), nullable=True),
        sa.Column("target_resource_id", sa.Uuid(), nullable=True),
        sa.Column("followup_index", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("reserved_budget_amount", sa.Numeric(precision=18, scale=6), server_default="0", nullable=False),
        sa.Column("budget_currency", sa.String(length=3), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="reserved", nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reservation_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("(actor_type='administrator' AND actor_administrator_id IS NOT NULL AND actor_agent_id IS NULL) OR (actor_type='agent' AND actor_agent_id IS NOT NULL AND actor_administrator_id IS NULL) OR (actor_type='system' AND actor_administrator_id IS NULL AND actor_agent_id IS NULL)", name="ck_authorization_usages_actor"),
        sa.CheckConstraint("quantity>0 AND reserved_budget_amount>=0", name="ck_authorization_usages_amounts"),
        sa.CheckConstraint("(reserved_budget_amount=0 AND budget_currency IS NULL) OR (reserved_budget_amount>0 AND budget_currency IS NOT NULL)", name="ck_authorization_usages_budget_currency"),
        sa.CheckConstraint("followup_index IS NULL OR followup_index>=0", name="ck_authorization_usages_followup"),
        sa.CheckConstraint("status IN ('reserved','succeeded','failed','released')", name="ck_authorization_usages_status"),
        sa.CheckConstraint("reservation_expires_at>reserved_at", name="ck_authorization_usages_reservation_expiry"),
        sa.CheckConstraint("(status='reserved' AND finalized_at IS NULL AND released_at IS NULL) OR (status IN ('succeeded','failed') AND finalized_at IS NOT NULL AND released_at IS NULL) OR (status='released' AND released_at IS NOT NULL)", name="ck_authorization_usages_lifecycle"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_authorization_usages_company_id_companies", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["authorization_policy_id"], ["authorization_policies.id"], name="fk_auth_usages_policy", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_administrator_id"], ["administrators.id"], name="fk_authorization_usages_actor_administrator_id_administrators", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reservation_key", name="uq_authorization_usages_reservation_key"),
    )
    op.create_index("uq_authorization_usages_execution", "authorization_usages", ["execution_id"], unique=True, postgresql_where=sa.text("execution_id IS NOT NULL"))
    op.create_index("ix_authorization_usages_policy_status_reserved", "authorization_usages", ["authorization_policy_id", "status", "reserved_at"])
    op.create_index("ix_authorization_usages_company_campaign_status_reserved", "authorization_usages", ["company_id", "campaign_id", "status", "reserved_at"])
    op.create_index("ix_authorization_usages_company_action_status_reserved", "authorization_usages", ["company_id", "action_type", "status", "reserved_at"])
    op.create_index("ix_authorization_usages_expiry_status", "authorization_usages", ["reservation_expires_at", "status"])
    op.create_index("ix_authorization_usages_company_target", "authorization_usages", ["company_id", "target_resource_type", "target_resource_id"])


def downgrade() -> None:
    """Remove authorization storage in reverse dependency order."""

    op.drop_index("ix_authorization_usages_company_target", table_name="authorization_usages")
    op.drop_index("ix_authorization_usages_expiry_status", table_name="authorization_usages")
    op.drop_index("ix_authorization_usages_company_action_status_reserved", table_name="authorization_usages")
    op.drop_index("ix_authorization_usages_company_campaign_status_reserved", table_name="authorization_usages")
    op.drop_index("ix_authorization_usages_policy_status_reserved", table_name="authorization_usages")
    op.drop_index("uq_authorization_usages_execution", table_name="authorization_usages")
    op.drop_table("authorization_usages")

    op.drop_index("ix_authorization_policies_source_decision", table_name="authorization_policies")
    op.drop_index("ix_authorization_policies_source_request", table_name="authorization_policies")
    op.drop_index("ix_authorization_policies_status_validity", table_name="authorization_policies")
    op.drop_index("ix_authorization_policies_company_subject_agent_status", table_name="authorization_policies")
    op.drop_index("ix_authorization_policies_company_subject_admin_status", table_name="authorization_policies")
    op.drop_index("ix_authorization_policies_company_campaign_status", table_name="authorization_policies")
    op.drop_index("ix_authorization_policies_company_tool_status", table_name="authorization_policies")
    op.drop_index("ix_authorization_policies_company_status_effect_action", table_name="authorization_policies")
    op.drop_table("authorization_policies")

    op.drop_index("ix_approval_decisions_company_approver_created_id", table_name="approval_decisions")
    op.drop_index("ix_approval_decisions_request_created_id", table_name="approval_decisions")
    op.drop_index("ix_approval_decisions_company_created_id", table_name="approval_decisions")
    op.drop_table("approval_decisions")

    op.drop_index("uq_approval_requests_pending_dedup", table_name="approval_requests")
    op.drop_index("ix_approval_requests_company_risk_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_company_campaign_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_company_action_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_company_requester_agent_created_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_company_requester_admin_created_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_company_status_created_id", table_name="approval_requests")
    op.drop_table("approval_requests")
