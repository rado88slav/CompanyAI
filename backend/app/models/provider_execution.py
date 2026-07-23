"""Company-scoped provider execution history."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class ProviderExecution(Base):
    __tablename__ = "provider_executions"
    __table_args__ = (UniqueConstraint("company_id", "id", name="uq_provider_executions_company_id"), UniqueConstraint("company_id", "idempotency_key", name="uq_provider_executions_company_idempotency"), ForeignKeyConstraint(["company_id", "provider_connection_id"], ["provider_connections.company_id", "provider_connections.id"], name="fk_provider_executions_company_connection", ondelete="RESTRICT"), CheckConstraint("status IN ('pending_authorization','authorized','running','succeeded','failed','cancelled','denied')", name="ck_provider_executions_status"), CheckConstraint("execution_mode IN ('dry_run','live')", name="ck_provider_executions_mode"), CheckConstraint("((requested_by_administrator_id IS NOT NULL)::int + (requested_by_agent_id IS NOT NULL)::int) = 1", name="ck_provider_executions_one_requester"), CheckConstraint("jsonb_typeof(request_payload)='object' AND jsonb_typeof(result_metadata)='object'", name="ck_provider_executions_json_objects"), Index("ix_provider_executions_company_created", "company_id", "created_at"))
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    provider_connection_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    provider_key: Mapped[str] = mapped_column(String(100), nullable=False)
    operation_key: Mapped[str] = mapped_column(String(100), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_authorization")
    requested_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    requested_by_agent_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("agents.id", ondelete="RESTRICT"))
    authorization_reference: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("authorization_policies.id", name="fk_provider_executions_authorization_policy", ondelete="RESTRICT"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    result_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    error_category: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class ProviderExecutionAttempt(Base):
    __tablename__ = "provider_execution_attempts"
    __table_args__ = (UniqueConstraint("company_id", "provider_execution_id", "attempt_number", name="uq_provider_execution_attempts_number"), ForeignKeyConstraint(["company_id", "provider_execution_id"], ["provider_executions.company_id", "provider_executions.id"], name="fk_provider_execution_attempts_execution", ondelete="RESTRICT"), CheckConstraint("attempt_number > 0", name="ck_provider_execution_attempts_number"), CheckConstraint("status IN ('running','succeeded','failed','cancelled')", name="ck_provider_execution_attempts_status"), Index("ix_provider_execution_attempts_execution", "company_id", "provider_execution_id"))
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4); company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False); provider_execution_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False); attempt_number: Mapped[int] = mapped_column(Integer, nullable=False); status: Mapped[str] = mapped_column(String(16), nullable=False); adapter_name: Mapped[str] = mapped_column(String(100), nullable=False); started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); request_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")); response_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")); error_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
