"""Create company memberships table.

Revision ID: 0006_company_memberships
Revises: 0005_audit_logs
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0006_company_memberships"
down_revision: str | None = "0005_audit_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("administrator_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'admin', 'operator', 'viewer')", name="ck_company_memberships_role"),
        sa.ForeignKeyConstraint(["administrator_id"], ["administrators.id"], name="fk_company_memberships_administrator_id_administrators", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_company_memberships_company_id_companies", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "administrator_id", name="uq_company_memberships_company_administrator"),
    )
    op.create_index("ix_company_memberships_administrator_active_company", "company_memberships", ["administrator_id", "is_active", "company_id"])
    op.create_index("ix_company_memberships_company_active_role", "company_memberships", ["company_id", "is_active", "role"])
    op.create_index("ix_company_memberships_company_created_id", "company_memberships", ["company_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_company_memberships_company_created_id", table_name="company_memberships")
    op.drop_index("ix_company_memberships_company_active_role", table_name="company_memberships")
    op.drop_index("ix_company_memberships_administrator_active_company", table_name="company_memberships")
    op.drop_table("company_memberships")
