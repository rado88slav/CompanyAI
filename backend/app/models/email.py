"""Company-isolated records for the thin email workflow."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InboundEmail(Base):
    __tablename__ = "inbound_emails"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_inbound_emails_company_id"),
        UniqueConstraint("company_id", "external_message_id", name="uq_inbound_emails_company_external"),
        ForeignKeyConstraint(["company_id", "provider_connection_id"], ["provider_connections.company_id", "provider_connections.id"], name="fk_inbound_emails_company_connection", ondelete="RESTRICT"),
        CheckConstraint("status IN ('received','reply_drafted','awaiting_approval','approved','rejected','sent','send_failed')", name="ck_inbound_emails_status"),
        Index("ix_inbound_emails_company_received_id", "company_id", "received_at", "id"),
        Index("ix_inbound_emails_company_status", "company_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    provider_connection_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    external_message_id: Mapped[str] = mapped_column(String(200), nullable=False)
    sender_name: Mapped[str | None] = mapped_column(String(200))
    sender_email: Mapped[str] = mapped_column(String(254), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(254), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received", server_default="received")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class EmailReplyProposal(Base):
    __tablename__ = "email_reply_proposals"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_email_reply_proposals_company_id"),
        UniqueConstraint("company_id", "inbound_email_id", name="uq_email_reply_proposals_inbound"),
        UniqueConstraint("approval_request_id", name="uq_email_reply_proposals_approval"),
        ForeignKeyConstraint(["company_id", "inbound_email_id"], ["inbound_emails.company_id", "inbound_emails.id"], name="fk_email_reply_proposals_inbound", ondelete="RESTRICT"),
        CheckConstraint("status IN ('draft','awaiting_approval','approved','rejected','sent','send_failed')", name="ck_email_reply_proposals_status"),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="ck_email_reply_proposals_digest"),
        Index("ix_email_reply_proposals_company_status", "company_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    inbound_email_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(254), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default="draft")
    approval_request_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("approval_requests.id", ondelete="RESTRICT"))
    created_by_administrator_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class OutboundEmail(Base):
    __tablename__ = "outbound_emails"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_outbound_emails_company_id"),
        UniqueConstraint("company_id", "reply_proposal_id", name="uq_outbound_emails_proposal"),
        UniqueConstraint("company_id", "provider_execution_id", name="uq_outbound_emails_execution"),
        ForeignKeyConstraint(["company_id", "reply_proposal_id"], ["email_reply_proposals.company_id", "email_reply_proposals.id"], name="fk_outbound_emails_proposal", ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "provider_execution_id"], ["provider_executions.company_id", "provider_executions.id"], name="fk_outbound_emails_execution", ondelete="RESTRICT"),
        CheckConstraint("status IN ('pending','sent','failed')", name="ck_outbound_emails_status"),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="ck_outbound_emails_digest"),
        CheckConstraint("(status='sent' AND provider_message_id IS NOT NULL AND sent_at IS NOT NULL) OR status<>'sent'", name="ck_outbound_emails_sent_result"),
        Index("ix_outbound_emails_company_status", "company_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    reply_proposal_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    provider_execution_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(254), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
