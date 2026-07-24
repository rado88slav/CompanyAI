"""Require credential encryption key identifiers.

Revision ID: 0013_credential_keyring_contract
Revises: 0012_credential_keyring_expand
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_credential_keyring_contract"
down_revision: str | None = "0012_credential_keyring_expand"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NULL_KEY_ID_ERROR = (
    "Credential encryption key ID contract cannot be enforced while "
    "NULL references remain."
)


def upgrade() -> None:
    provider_credentials = sa.table(
        "provider_credentials",
        sa.column("encryption_key_id", sa.String(length=64)),
    )
    null_reference = op.get_bind().execute(
        sa.select(sa.literal(1))
        .select_from(provider_credentials)
        .where(provider_credentials.c.encryption_key_id.is_(None))
        .limit(1)
    ).first()
    if null_reference is not None:
        raise RuntimeError(_NULL_KEY_ID_ERROR)

    op.alter_column(
        "provider_credentials",
        "encryption_key_id",
        existing_type=sa.String(length=64),
        existing_nullable=True,
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "provider_credentials",
        "encryption_key_id",
        existing_type=sa.String(length=64),
        existing_nullable=False,
        nullable=True,
    )
