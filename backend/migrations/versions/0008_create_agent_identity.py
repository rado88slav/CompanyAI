"""Create Agent Identity and Internal Agent Authentication storage.

Revision ID: 0008_agent_identity
Revises: 0007_approval_manager
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_agent_identity"
down_revision: str | None = "0007_approval_manager"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create schema only; no agents, credentials or permissions are inserted."""
    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("agent_type", sa.String(32), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_by_administrator_id", sa.Uuid(), nullable=False),
        sa.Column("updated_by_administrator_id", sa.Uuid(), nullable=True),
        sa.Column("revoked_by_administrator_id", sa.Uuid(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(1000), nullable=True),
        sa.Column("auth_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active','inactive','revoked')", name="ck_agents_status"),
        sa.CheckConstraint("agent_type IN ('email_outreach','phone_campaign','lead_research','campaign_manager','general','custom')", name="ck_agents_type"),
        sa.CheckConstraint("length(trim(name)) >= 2", name="ck_agents_name"),
        sa.CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_agents_slug"),
        sa.CheckConstraint("auth_version > 0", name="ck_agents_auth_version"),
        sa.CheckConstraint("jsonb_typeof(metadata)='object'", name="ck_agents_metadata_object"),
        sa.CheckConstraint("(status='revoked' AND revoked_at IS NOT NULL AND revoked_by_administrator_id IS NOT NULL) OR status<>'revoked'", name="ck_agents_revocation"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_agents_company", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_administrator_id"], ["administrators.id"], name="fk_agents_created_by_admin", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_administrator_id"], ["administrators.id"], name="fk_agents_updated_by_admin", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by_administrator_id"], ["administrators.id"], name="fk_agents_revoked_by_admin", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "slug", name="uq_agents_company_slug"),
        sa.UniqueConstraint("company_id", "id", name="uq_agents_company_id_id"),
    )
    op.create_index("ix_agents_company_status_created_id", "agents", ["company_id", "status", "created_at", "id"])
    op.create_index("ix_agents_company_type_status", "agents", ["company_id", "agent_type", "status"])

    op.create_table(
        "agent_credentials",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("company_id", sa.Uuid(), nullable=False), sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False), sa.Column("public_id", sa.String(64), nullable=False), sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("secret_prefix", sa.String(32), nullable=False), sa.Column("secret_last_four", sa.String(4), nullable=False), sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column("created_by_administrator_id", sa.Uuid(), nullable=False), sa.Column("revoked_by_administrator_id", sa.Uuid(), nullable=True), sa.Column("rotated_from_credential_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True), sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True), sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(1000), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active','revoked','rotated','expired')", name="ck_agent_credentials_status"), sa.CheckConstraint("length(trim(name)) > 0", name="ck_agent_credentials_name"),
        sa.CheckConstraint("length(public_id) >= 16", name="ck_agent_credentials_public_id"), sa.CheckConstraint("length(secret_hash) = 64", name="ck_agent_credentials_hash"), sa.CheckConstraint("length(secret_last_four) = 4", name="ck_agent_credentials_last_four"),
        sa.ForeignKeyConstraint(["company_id", "agent_id"], ["agents.company_id", "agents.id"], name="fk_agent_credentials_company_agent", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_administrator_id"], ["administrators.id"], name="fk_agent_credentials_created_admin", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by_administrator_id"], ["administrators.id"], name="fk_agent_credentials_revoked_admin", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id", "agent_id", "rotated_from_credential_id"], ["agent_credentials.company_id", "agent_credentials.agent_id", "agent_credentials.id"], name="fk_agent_credentials_rotation_lineage", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("public_id", name="uq_agent_credentials_public_id"),
        sa.UniqueConstraint("company_id", "agent_id", "id", name="uq_agent_credentials_company_agent_id"),
    )
    op.create_index("ix_agent_credentials_company_agent_status", "agent_credentials", ["company_id", "agent_id", "status"])
    op.create_index("ix_agent_credentials_public_status", "agent_credentials", ["public_id", "status"])

    op.create_table(
        "agent_permissions",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("company_id", sa.Uuid(), nullable=False), sa.Column("agent_id", sa.Uuid(), nullable=False), sa.Column("permission_key", sa.String(150), nullable=False),
        sa.Column("status", sa.String(16), server_default="active", nullable=False), sa.Column("granted_by_administrator_id", sa.Uuid(), nullable=False), sa.Column("revoked_by_administrator_id", sa.Uuid(), nullable=True),
        sa.Column("grant_reason", sa.String(1000), nullable=True), sa.Column("revocation_reason", sa.String(1000), nullable=True), sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active','revoked')", name="ck_agent_permissions_status"), sa.CheckConstraint("permission_key ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$'", name="ck_agent_permissions_key"),
        sa.ForeignKeyConstraint(["company_id", "agent_id"], ["agents.company_id", "agents.id"], name="fk_agent_permissions_company_agent", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["granted_by_administrator_id"], ["administrators.id"], name="fk_agent_permissions_granted_admin", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by_administrator_id"], ["administrators.id"], name="fk_agent_permissions_revoked_admin", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_agent_permissions_active_key", "agent_permissions", ["company_id", "agent_id", "permission_key"], unique=True, postgresql_where=sa.text("status = 'active'"))
    op.create_index("ix_agent_permissions_company_agent_status", "agent_permissions", ["company_id", "agent_id", "status"])

    op.add_column("audit_logs", sa.Column("actor_agent_id", sa.Uuid(), nullable=True))
    op.drop_constraint("ck_audit_logs_actor_type", "audit_logs", type_="check")
    op.drop_constraint("ck_audit_logs_actor_administrator", "audit_logs", type_="check")
    op.create_check_constraint("ck_audit_logs_actor_type", "audit_logs", "actor_type IN ('administrator','agent','system')")
    op.create_check_constraint("ck_audit_logs_actor_administrator", "audit_logs", "(actor_type='administrator' AND actor_administrator_id IS NOT NULL AND actor_agent_id IS NULL) OR (actor_type='agent' AND actor_administrator_id IS NULL AND actor_agent_id IS NOT NULL) OR (actor_type='system' AND actor_administrator_id IS NULL AND actor_agent_id IS NULL)")
    op.create_foreign_key("fk_audit_logs_actor_agent", "audit_logs", "agents", ["actor_agent_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_audit_logs_actor_agent_created_id", "audit_logs", ["actor_agent_id", "created_at", "id"])

    op.create_foreign_key("fk_approval_requests_requester_agent", "approval_requests", "agents", ["requester_agent_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_auth_policies_subject_agent", "authorization_policies", "agents", ["subject_agent_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_auth_usages_actor_agent", "authorization_usages", "agents", ["actor_agent_id"], ["id"], ondelete="RESTRICT")


def downgrade() -> None:
    """Remove agent references before agent-owned tables."""
    op.drop_constraint("fk_auth_usages_actor_agent", "authorization_usages", type_="foreignkey")
    op.drop_constraint("fk_auth_policies_subject_agent", "authorization_policies", type_="foreignkey")
    op.drop_constraint("fk_approval_requests_requester_agent", "approval_requests", type_="foreignkey")
    op.drop_index("ix_audit_logs_actor_agent_created_id", table_name="audit_logs")
    op.drop_constraint("fk_audit_logs_actor_agent", "audit_logs", type_="foreignkey")
    op.drop_constraint("ck_audit_logs_actor_administrator", "audit_logs", type_="check")
    op.drop_constraint("ck_audit_logs_actor_type", "audit_logs", type_="check")
    op.create_check_constraint("ck_audit_logs_actor_type", "audit_logs", "actor_type IN ('administrator','system')")
    op.create_check_constraint("ck_audit_logs_actor_administrator", "audit_logs", "(actor_type='administrator' AND actor_administrator_id IS NOT NULL) OR (actor_type='system' AND actor_administrator_id IS NULL)")
    op.drop_column("audit_logs", "actor_agent_id")
    op.drop_index("ix_agent_permissions_company_agent_status", table_name="agent_permissions")
    op.drop_index("uq_agent_permissions_active_key", table_name="agent_permissions")
    op.drop_table("agent_permissions")
    op.drop_index("ix_agent_credentials_public_status", table_name="agent_credentials")
    op.drop_index("ix_agent_credentials_company_agent_status", table_name="agent_credentials")
    op.drop_table("agent_credentials")
    op.drop_index("ix_agents_company_type_status", table_name="agents")
    op.drop_index("ix_agents_company_status_created_id", table_name="agents")
    op.drop_table("agents")
