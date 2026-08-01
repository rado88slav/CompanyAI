"""Allow live provider execution outcome states.

Revision ID: 0015_live_execution_outcomes
Revises: 0014_email_workflow
Create Date: 2026-08-01 00:00:00.000000
"""

from alembic import op

revision = "0015_live_execution_outcomes"
down_revision = "0014_email_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_provider_execution_attempts_status", "provider_execution_attempts", type_="check")
    op.drop_constraint("ck_provider_executions_status", "provider_executions", type_="check")
    op.create_check_constraint(
        "ck_provider_executions_status",
        "provider_executions",
        "status IN ('pending_authorization','authorized','running','succeeded','failed','failed_before_send','outcome_uncertain','cancelled','denied')",
    )
    op.create_check_constraint(
        "ck_provider_execution_attempts_status",
        "provider_execution_attempts",
        "status IN ('running','succeeded','failed','failed_before_send','outcome_uncertain','cancelled')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_provider_execution_attempts_status", "provider_execution_attempts", type_="check")
    op.drop_constraint("ck_provider_executions_status", "provider_executions", type_="check")
    op.create_check_constraint(
        "ck_provider_executions_status",
        "provider_executions",
        "status IN ('pending_authorization','authorized','running','succeeded','failed','cancelled','denied')",
    )
    op.create_check_constraint(
        "ck_provider_execution_attempts_status",
        "provider_execution_attempts",
        "status IN ('running','succeeded','failed','cancelled')",
    )
