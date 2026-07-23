"""Create provider execution history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011_provider_execution"
down_revision = "0010_provider_connections"
branch_labels: str | Sequence[str] | None = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_executions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("provider_connection_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(100), nullable=False),
        sa.Column("operation_key", sa.String(100), nullable=False),
        sa.Column("execution_mode", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("requested_by_administrator_id", sa.Uuid()),
        sa.Column("requested_by_agent_id", sa.Uuid()),
        sa.Column("authorization_reference", sa.Uuid()),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("result_metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error_category", sa.String(64)),
        sa.Column("error_message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id", "provider_connection_id"], ["provider_connections.company_id", "provider_connections.id"], name="fk_provider_executions_company_connection", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_administrator_id"], ["administrators.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["authorization_reference"], ["authorization_policies.id"], name="fk_provider_executions_authorization_policy", ondelete="RESTRICT"),
        sa.UniqueConstraint("company_id", "id", name="uq_provider_executions_company_id"),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_provider_executions_company_idempotency"),
        sa.CheckConstraint("status IN ('pending_authorization','authorized','running','succeeded','failed','cancelled','denied')", name="ck_provider_executions_status"),
        sa.CheckConstraint("execution_mode IN ('dry_run','live')", name="ck_provider_executions_mode"),
        sa.CheckConstraint("((requested_by_administrator_id IS NOT NULL)::int + (requested_by_agent_id IS NOT NULL)::int) = 1", name="ck_provider_executions_one_requester"),
        sa.CheckConstraint("jsonb_typeof(request_payload)='object' AND jsonb_typeof(result_metadata)='object'", name="ck_provider_executions_json_objects"),
    )
    op.create_index("ix_provider_executions_company_created", "provider_executions", ["company_id", "created_at"])
    op.create_index("ix_provider_executions_authorization_reference", "provider_executions", ["authorization_reference"])
    op.create_table(
        "provider_execution_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("provider_execution_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("adapter_name", sa.String(100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("request_metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("response_metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error_metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["company_id", "provider_execution_id"], ["provider_executions.company_id", "provider_executions.id"], name="fk_provider_execution_attempts_execution", ondelete="RESTRICT"),
        sa.UniqueConstraint("company_id", "provider_execution_id", "attempt_number", name="uq_provider_execution_attempts_number"),
        sa.CheckConstraint("attempt_number > 0", name="ck_provider_execution_attempts_number"),
        sa.CheckConstraint("status IN ('running','succeeded','failed','cancelled')", name="ck_provider_execution_attempts_status"),
    )
    op.create_index("ix_provider_execution_attempts_execution", "provider_execution_attempts", ["company_id", "provider_execution_id"])
    op.create_foreign_key(
        "fk_authorization_usages_provider_execution",
        "authorization_usages",
        "provider_executions",
        ["company_id", "execution_id"],
        ["company_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_authorization_usages_provider_execution", "authorization_usages", type_="foreignkey")
    op.drop_index("ix_provider_execution_attempts_execution", table_name="provider_execution_attempts")
    op.drop_table("provider_execution_attempts")
    op.drop_index("ix_provider_executions_authorization_reference", table_name="provider_executions")
    op.drop_index("ix_provider_executions_company_created", table_name="provider_executions")
    op.drop_table("provider_executions")
