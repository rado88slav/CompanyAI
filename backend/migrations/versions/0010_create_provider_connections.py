"""Create provider connection metadata and encrypted credential history.

Revision ID: 0010_provider_connections
Revises: 0009_tool_registry
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_provider_connections"
down_revision: str | None = "0009_tool_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("authentication_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), server_default="inactive", nullable=False),
        sa.Column("configuration", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_by_administrator_id", sa.Uuid()),
        sa.Column("updated_by_administrator_id", sa.Uuid()),
        sa.Column("activated_by_administrator_id", sa.Uuid()),
        sa.Column("deactivated_by_administrator_id", sa.Uuid()),
        sa.Column("revoked_by_administrator_id", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("deactivated_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("provider_key ~ '^[a-z][a-z0-9_]*$'", name="ck_provider_connections_key"),
        sa.CheckConstraint("status IN ('inactive','active','revoked')", name="ck_provider_connections_status"),
        sa.CheckConstraint("jsonb_typeof(configuration)='object'", name="ck_provider_connections_config_object"),
        sa.CheckConstraint("jsonb_typeof(metadata)='object'", name="ck_provider_connections_metadata_object"),
        sa.CheckConstraint("(status='active' AND activated_at IS NOT NULL AND activated_by_administrator_id IS NOT NULL) OR status<>'active'", name="ck_provider_connections_activation"),
        sa.CheckConstraint("(status='revoked' AND revoked_at IS NOT NULL AND revoked_by_administrator_id IS NOT NULL) OR status<>'revoked'", name="ck_provider_connections_revocation"),
        sa.CheckConstraint("(deactivated_at IS NULL) = (deactivated_by_administrator_id IS NULL)", name="ck_provider_connections_deactivation_actor"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_provider_connections_company", ondelete="RESTRICT"),
        *[sa.ForeignKeyConstraint([field], ["administrators.id"], name=f"fk_provider_connections_{prefix}_admin", ondelete="RESTRICT") for field, prefix in (("created_by_administrator_id","created"),("updated_by_administrator_id","updated"),("activated_by_administrator_id","activated"),("deactivated_by_administrator_id","deactivated"),("revoked_by_administrator_id","revoked"))],
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "slug", name="uq_provider_connections_company_slug"),
        sa.UniqueConstraint("company_id", "id", name="uq_provider_connections_company_id"),
    )
    op.create_index("ix_provider_connections_company_status_provider", "provider_connections", ["company_id", "status", "provider_key"])
    op.create_table(
        "provider_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("provider_connection_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column("encrypted_payload", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("encryption_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("credential_schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("rotated_from_credential_id", sa.Uuid()),
        sa.Column("created_by_administrator_id", sa.Uuid()),
        sa.Column("revoked_by_administrator_id", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('active','rotated','revoked','expired')", name="ck_provider_credentials_status"),
        sa.CheckConstraint("(status='revoked' AND revoked_at IS NOT NULL AND revoked_by_administrator_id IS NOT NULL) OR status<>'revoked'", name="ck_provider_credentials_revocation"),
        sa.CheckConstraint("octet_length(nonce)=12", name="ck_provider_credentials_nonce"),
        sa.CheckConstraint("encryption_version > 0 AND credential_schema_version > 0", name="ck_provider_credentials_versions"),
        sa.ForeignKeyConstraint(["company_id","provider_connection_id"], ["provider_connections.company_id","provider_connections.id"], name="fk_provider_credentials_company_connection", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id","provider_connection_id","rotated_from_credential_id"], ["provider_credentials.company_id","provider_credentials.provider_connection_id","provider_credentials.id"], name="fk_provider_credentials_rotation", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_administrator_id"], ["administrators.id"], name="fk_provider_credentials_created_admin", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by_administrator_id"], ["administrators.id"], name="fk_provider_credentials_revoked_admin", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id","provider_connection_id","id", name="uq_provider_credentials_identity"),
    )
    op.create_index("uq_provider_credentials_active", "provider_credentials", ["company_id","provider_connection_id"], unique=True, postgresql_where=sa.text("status='active'"))
    op.create_index("ix_provider_credentials_connection_created", "provider_credentials", ["company_id","provider_connection_id","created_at"])


def downgrade() -> None:
    op.drop_index("ix_provider_credentials_connection_created", table_name="provider_credentials")
    op.drop_index("uq_provider_credentials_active", table_name="provider_credentials")
    op.drop_table("provider_credentials")
    op.drop_index("ix_provider_connections_company_status_provider", table_name="provider_connections")
    op.drop_table("provider_connections")
