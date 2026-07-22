"""Company-owned agent identity, credential and exact permission models."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentType(StrEnum):
    EMAIL_OUTREACH = "email_outreach"
    PHONE_CAMPAIGN = "phone_campaign"
    LEAD_RESEARCH = "lead_research"
    CAMPAIGN_MANAGER = "campaign_manager"
    GENERAL = "general"
    CUSTOM = "custom"


class AgentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    REVOKED = "revoked"


class AgentCredentialStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    ROTATED = "rotated"
    EXPIRED = "expired"


class AgentPermissionStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("company_id", "slug", name="uq_agents_company_slug"),
        UniqueConstraint("company_id", "id", name="uq_agents_company_id_id"),
        CheckConstraint("status IN ('active','inactive','revoked')", name="ck_agents_status"),
        CheckConstraint("agent_type IN ('email_outreach','phone_campaign','lead_research','campaign_manager','general','custom')", name="ck_agents_type"),
        CheckConstraint("length(trim(name)) >= 2", name="ck_agents_name"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_agents_slug"),
        CheckConstraint("auth_version > 0", name="ck_agents_auth_version"),
        CheckConstraint("jsonb_typeof(metadata)='object'", name="ck_agents_metadata_object"),
        CheckConstraint("(status='revoked' AND revoked_at IS NOT NULL AND revoked_by_administrator_id IS NOT NULL) OR status<>'revoked'", name="ck_agents_revocation"),
        Index("ix_agents_company_status_created_id", "company_id", "status", "created_at", "id"),
        Index("ix_agents_company_type_status", "company_id", "agent_type", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_by_administrator_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"), nullable=False)
    updated_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    revoked_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(String(1000))
    auth_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AgentCredential(Base):
    __tablename__ = "agent_credentials"
    __table_args__ = (
        ForeignKeyConstraint(["company_id", "agent_id"], ["agents.company_id", "agents.id"], name="fk_agent_credentials_company_agent", ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["company_id", "agent_id", "rotated_from_credential_id"],
            ["agent_credentials.company_id", "agent_credentials.agent_id", "agent_credentials.id"],
            name="fk_agent_credentials_rotation_lineage",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("public_id", name="uq_agent_credentials_public_id"),
        UniqueConstraint("company_id", "agent_id", "id", name="uq_agent_credentials_company_agent_id"),
        CheckConstraint("status IN ('active','revoked','rotated','expired')", name="ck_agent_credentials_status"),
        CheckConstraint("length(trim(name)) > 0", name="ck_agent_credentials_name"),
        CheckConstraint("length(public_id) >= 16", name="ck_agent_credentials_public_id"),
        CheckConstraint("length(secret_hash) = 64", name="ck_agent_credentials_hash"),
        CheckConstraint("length(secret_last_four) = 4", name="ck_agent_credentials_last_four"),
        Index("ix_agent_credentials_company_agent_status", "company_id", "agent_id", "status"),
        Index("ix_agent_credentials_public_status", "public_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    agent_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    secret_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    secret_last_four: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    created_by_administrator_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"), nullable=False)
    revoked_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    rotated_from_credential_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AgentPermission(Base):
    __tablename__ = "agent_permissions"
    __table_args__ = (
        ForeignKeyConstraint(["company_id", "agent_id"], ["agents.company_id", "agents.id"], name="fk_agent_permissions_company_agent", ondelete="RESTRICT"),
        CheckConstraint("status IN ('active','revoked')", name="ck_agent_permissions_status"),
        CheckConstraint("permission_key ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$'", name="ck_agent_permissions_key"),
        Index("uq_agent_permissions_active_key", "company_id", "agent_id", "permission_key", unique=True, postgresql_where=text("status = 'active'")),
        Index("ix_agent_permissions_company_agent_status", "company_id", "agent_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    agent_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    permission_key: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    granted_by_administrator_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"), nullable=False)
    revoked_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    grant_reason: Mapped[str | None] = mapped_column(String(1000))
    revocation_reason: Mapped[str | None] = mapped_column(String(1000))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
