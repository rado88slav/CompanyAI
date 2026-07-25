"""Create the thin email workflow schema.

Revision ID: 0014_email_workflow
Revises: 0013_credential_keyring_contract
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_email_workflow"
down_revision = "0013_credential_keyring_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_approval_requests_company_id",
        "approval_requests",
        ["company_id", "id"],
    )
    op.create_table(
        "inbound_emails",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("provider_connection_id", sa.Uuid(), nullable=True),
        sa.Column("external_message_id", sa.String(200), nullable=False),
        sa.Column("sender_name", sa.String(200), nullable=True),
        sa.Column("sender_email", sa.String(254), nullable=False),
        sa.Column("recipient_email", sa.String(254), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), server_default="received", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_inbound_emails_company_id"),
        sa.UniqueConstraint("company_id", "external_message_id", name="uq_inbound_emails_company_external"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id", "provider_connection_id"], ["provider_connections.company_id", "provider_connections.id"], name="fk_inbound_emails_company_connection", ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('received','reply_drafted','awaiting_approval','approved','rejected','sent','send_failed')", name="ck_inbound_emails_status"),
    )
    op.create_index("ix_inbound_emails_company_received_id", "inbound_emails", ["company_id", "received_at", "id"])
    op.create_index("ix_inbound_emails_company_status", "inbound_emails", ["company_id", "status"])
    op.create_table(
        "email_reply_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("inbound_email_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_email", sa.String(254), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="draft", nullable=False),
        sa.Column("approval_request_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_administrator_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_email_reply_proposals_company_id"),
        sa.UniqueConstraint("company_id", "inbound_email_id", name="uq_email_reply_proposals_inbound"),
        sa.UniqueConstraint("approval_request_id", name="uq_email_reply_proposals_approval"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id", "inbound_email_id"], ["inbound_emails.company_id", "inbound_emails.id"], name="fk_email_reply_proposals_inbound", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id", "approval_request_id"], ["approval_requests.company_id", "approval_requests.id"], name="fk_email_reply_proposals_company_approval", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_administrator_id"], ["administrators.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('draft','awaiting_approval','approved','rejected','sent','send_failed')", name="ck_email_reply_proposals_status"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="ck_email_reply_proposals_digest"),
    )
    op.create_index("ix_email_reply_proposals_company_status", "email_reply_proposals", ["company_id", "status"])
    op.create_table(
        "outbound_emails",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("reply_proposal_id", sa.Uuid(), nullable=False),
        sa.Column("provider_execution_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_email", sa.String(254), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("provider_message_id", sa.String(200), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_outbound_emails_company_id"),
        sa.UniqueConstraint("company_id", "reply_proposal_id", name="uq_outbound_emails_proposal"),
        sa.UniqueConstraint("company_id", "provider_execution_id", name="uq_outbound_emails_execution"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id", "reply_proposal_id"], ["email_reply_proposals.company_id", "email_reply_proposals.id"], name="fk_outbound_emails_proposal", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id", "provider_execution_id"], ["provider_executions.company_id", "provider_executions.id"], name="fk_outbound_emails_execution", ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('pending','sent','failed')", name="ck_outbound_emails_status"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="ck_outbound_emails_digest"),
        sa.CheckConstraint("(status='sent' AND provider_message_id IS NOT NULL AND sent_at IS NOT NULL) OR (status<>'sent' AND provider_message_id IS NULL AND sent_at IS NULL)", name="ck_outbound_emails_sent_result"),
    )
    op.create_index("ix_outbound_emails_company_status", "outbound_emails", ["company_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_outbound_emails_company_status", table_name="outbound_emails")
    op.drop_table("outbound_emails")
    op.drop_index("ix_email_reply_proposals_company_status", table_name="email_reply_proposals")
    op.drop_table("email_reply_proposals")
    op.drop_index("ix_inbound_emails_company_status", table_name="inbound_emails")
    op.drop_index("ix_inbound_emails_company_received_id", table_name="inbound_emails")
    op.drop_table("inbound_emails")
    op.drop_constraint(
        "uq_approval_requests_company_id",
        "approval_requests",
        type_="unique",
    )
