"""Expand provider credentials for encryption keyring metadata.

Revision ID: 0012_credential_keyring_expand
Revises: 0011_provider_execution
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_credential_keyring_expand"
down_revision: str | None = "0011_provider_execution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "provider_credentials",
        sa.Column("encryption_key_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "provider_credentials",
        sa.Column(
            "encryption_revision",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "ck_provider_credentials_encryption_revision",
        "provider_credentials",
        "encryption_revision >= 0",
    )
    op.create_check_constraint(
        "ck_provider_credentials_encryption_key_id",
        "provider_credentials",
        (
            "encryption_key_id IS NULL OR "
            "encryption_key_id ~ '^[a-z][a-z0-9_-]{0,63}$'"
        ),
    )
    op.create_index(
        "ix_provider_credentials_encryption_key_id_id",
        "provider_credentials",
        ["encryption_key_id", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provider_credentials_encryption_key_id_id",
        table_name="provider_credentials",
    )
    op.drop_constraint(
        "ck_provider_credentials_encryption_key_id",
        "provider_credentials",
        type_="check",
    )
    op.drop_constraint(
        "ck_provider_credentials_encryption_revision",
        "provider_credentials",
        type_="check",
    )
    op.drop_column("provider_credentials", "encryption_revision")
    op.drop_column("provider_credentials", "encryption_key_id")
