"""Create administrators table.

Revision ID: 0004_administrators
Revises: 0003_company_settings
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_administrators"
down_revision: str | None = "0003_company_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the administrators table."""

    op.create_table(
        "administrators",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "email",
            sa.String(length=320),
            nullable=False,
        ),
        sa.Column(
            "full_name",
            sa.String(length=200),
            nullable=False,
        ),
        sa.Column(
            "password_hash",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "is_superuser",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(email) >= 3",
            name="ck_administrators_email_not_empty",
        ),
        sa.CheckConstraint(
            "email = lower(email)",
            name="ck_administrators_email_lowercase",
        ),
        sa.CheckConstraint(
            "length(full_name) >= 2",
            name="ck_administrators_full_name_not_empty",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "email",
            name="uq_administrators_email",
        ),
    )


def downgrade() -> None:
    """Remove the administrators table."""

    op.drop_table("administrators")
