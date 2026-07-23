"""Create secure Tool Registry metadata and grant storage.

Revision ID: 0009_tool_registry
Revises: 0008_agent_identity
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_tool_registry"
down_revision: str | None = "0008_agent_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create schema only; no tools, company availability or grants are inserted."""

    op.create_table(
        "tool_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(150), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("execution_mode", sa.String(32), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column("input_schema", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("output_schema", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by_administrator_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("key ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$'", name="ck_tool_definitions_key"),
        sa.CheckConstraint("status IN ('active','inactive','deprecated')", name="ck_tool_definitions_status"),
        sa.CheckConstraint("risk_level IN ('low','medium','high','critical')", name="ck_tool_definitions_risk"),
        sa.CheckConstraint("execution_mode IN ('internal','provider','external_executor')", name="ck_tool_definitions_execution_mode"),
        sa.CheckConstraint("risk_level NOT IN ('high','critical') OR requires_approval", name="ck_tool_definitions_risk_approval"),
        sa.CheckConstraint("jsonb_typeof(input_schema)='object'", name="ck_tool_definitions_input_object"),
        sa.CheckConstraint("jsonb_typeof(output_schema)='object'", name="ck_tool_definitions_output_object"),
        sa.CheckConstraint("jsonb_typeof(metadata)='object'", name="ck_tool_definitions_metadata_object"),
        sa.ForeignKeyConstraint(["created_by_administrator_id"], ["administrators.id"], name="fk_tool_definitions_created_admin", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_tool_definitions_key"),
    )
    op.create_index("ix_tool_definitions_status_category_key", "tool_definitions", ["status", "category", "key"])
    op.create_index("ix_tool_definitions_risk_status", "tool_definitions", ["risk_level", "status"])

    op.create_table(
        "company_tools",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("tool_definition_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("enabled_by_administrator_id", sa.Uuid(), nullable=True),
        sa.Column("disabled_by_administrator_id", sa.Uuid(), nullable=True),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('enabled','disabled')", name="ck_company_tools_status"),
        sa.CheckConstraint("(status='enabled' AND enabled_at IS NOT NULL) OR status='disabled'", name="ck_company_tools_enabled_at"),
        sa.CheckConstraint("(status='disabled' AND disabled_at IS NOT NULL) OR status='enabled'", name="ck_company_tools_disabled_at"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_company_tools_company", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tool_definition_id"], ["tool_definitions.id"], name="fk_company_tools_definition", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["enabled_by_administrator_id"], ["administrators.id"], name="fk_company_tools_enabled_admin", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["disabled_by_administrator_id"], ["administrators.id"], name="fk_company_tools_disabled_admin", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "tool_definition_id", name="uq_company_tools_company_tool"),
    )
    op.create_index("ix_company_tools_company_status_tool", "company_tools", ["company_id", "status", "tool_definition_id"])

    op.create_table(
        "agent_tool_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("tool_definition_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column("granted_by_administrator_id", sa.Uuid(), nullable=True),
        sa.Column("revoked_by_administrator_id", sa.Uuid(), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active','revoked')", name="ck_agent_tool_grants_status"),
        sa.CheckConstraint("(status='revoked' AND revoked_at IS NOT NULL) OR status='active'", name="ck_agent_tool_grants_revocation"),
        sa.ForeignKeyConstraint(["company_id", "agent_id"], ["agents.company_id", "agents.id"], name="fk_agent_tool_grants_company_agent", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id", "tool_definition_id"], ["company_tools.company_id", "company_tools.tool_definition_id"], name="fk_agent_tool_grants_company_tool", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["granted_by_administrator_id"], ["administrators.id"], name="fk_agent_tool_grants_granted_admin", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by_administrator_id"], ["administrators.id"], name="fk_agent_tool_grants_revoked_admin", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_agent_tool_grants_active", "agent_tool_grants", ["company_id", "agent_id", "tool_definition_id"], unique=True, postgresql_where=sa.text("status = 'active'"))
    op.create_index("ix_agent_tool_grants_company_agent_status", "agent_tool_grants", ["company_id", "agent_id", "status"])


def downgrade() -> None:
    """Remove Tool Registry schema without touching revision 0008."""

    op.drop_index("ix_agent_tool_grants_company_agent_status", table_name="agent_tool_grants")
    op.drop_index("uq_agent_tool_grants_active", table_name="agent_tool_grants")
    op.drop_table("agent_tool_grants")
    op.drop_index("ix_company_tools_company_status_tool", table_name="company_tools")
    op.drop_table("company_tools")
    op.drop_index("ix_tool_definitions_risk_status", table_name="tool_definitions")
    op.drop_index("ix_tool_definitions_status_category_key", table_name="tool_definitions")
    op.drop_table("tool_definitions")
