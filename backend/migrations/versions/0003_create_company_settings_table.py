"""Create company settings table.

Revision ID: 0003_company_settings
Revises: 0002_companies
Create Date: 2026-07-22
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_company_settings"
down_revision: Union[str, Sequence[str], None] = (
    "0002_companies"
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the company_settings table and indexes."""

    op.create_table(
        "company_settings",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "key",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "value",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(category) > 0",
            name="ck_company_settings_category_not_empty",
        ),
        sa.CheckConstraint(
            "length(key) > 0",
            name="ck_company_settings_key_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_company_settings_company_id_companies",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "category",
            "key",
            name="uq_company_settings_company_category_key",
        ),
    )


def downgrade() -> None:
    """Remove the company_settings table."""

    op.drop_table("company_settings")
