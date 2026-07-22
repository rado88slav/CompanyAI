"""Create append-only audit logs table.

Revision ID: 0005_audit_logs
Revises: 0004_administrators
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_audit_logs"
down_revision: str | None = "0004_administrators"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create audit storage, constraints and investigation indexes."""

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_administrator_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "scope IN ('company', 'platform')",
            name="ck_audit_logs_scope",
        ),
        sa.CheckConstraint(
            "actor_type IN ('administrator', 'system')",
            name="ck_audit_logs_actor_type",
        ),
        sa.CheckConstraint(
            "(scope = 'company' AND company_id IS NOT NULL) OR "
            "(scope = 'platform' AND company_id IS NULL)",
            name="ck_audit_logs_scope_company",
        ),
        sa.CheckConstraint(
            "(actor_type = 'administrator' AND "
            "actor_administrator_id IS NOT NULL) OR "
            "(actor_type = 'system' AND "
            "actor_administrator_id IS NULL)",
            name="ck_audit_logs_actor_administrator",
        ),
        sa.CheckConstraint(
            "length(trim(action)) > 0",
            name="ck_audit_logs_action_not_empty",
        ),
        sa.CheckConstraint(
            "length(trim(resource_type)) > 0",
            name="ck_audit_logs_resource_type_not_empty",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(details) = 'object'",
            name="ck_audit_logs_details_object",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_audit_logs_company_id_companies",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_administrator_id"],
            ["administrators.id"],
            name="fk_audit_logs_actor_administrator_id_administrators",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_logs_company_created_id",
        "audit_logs",
        ["company_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_audit_logs_actor_created_id",
        "audit_logs",
        ["actor_administrator_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_audit_logs_action_created_id",
        "audit_logs",
        ["action", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_audit_logs_resource_created_id",
        "audit_logs",
        ["resource_type", "resource_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove append-only audit storage."""

    op.drop_index("ix_audit_logs_resource_created_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action_created_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_created_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_company_created_id", table_name="audit_logs")
    op.drop_table("audit_logs")
