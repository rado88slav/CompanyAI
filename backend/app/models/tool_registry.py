"""Global tool catalog, company availability and agent grants."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ToolStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


class ToolRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolExecutionMode(StrEnum):
    INTERNAL = "internal"
    PROVIDER = "provider"
    EXTERNAL_EXECUTOR = "external_executor"


class CompanyToolStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class AgentToolGrantStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class ToolDefinition(Base):
    __tablename__ = "tool_definitions"
    __table_args__ = (
        UniqueConstraint("key", name="uq_tool_definitions_key"),
        CheckConstraint("key ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$'", name="ck_tool_definitions_key"),
        CheckConstraint("status IN ('active','inactive','deprecated')", name="ck_tool_definitions_status"),
        CheckConstraint("risk_level IN ('low','medium','high','critical')", name="ck_tool_definitions_risk"),
        CheckConstraint("execution_mode IN ('internal','provider','external_executor')", name="ck_tool_definitions_execution_mode"),
        CheckConstraint("risk_level NOT IN ('high','critical') OR requires_approval", name="ck_tool_definitions_risk_approval"),
        CheckConstraint("jsonb_typeof(input_schema)='object'", name="ck_tool_definitions_input_object"),
        CheckConstraint("jsonb_typeof(output_schema)='object'", name="ck_tool_definitions_output_object"),
        CheckConstraint("jsonb_typeof(metadata)='object'", name="ck_tool_definitions_metadata_object"),
        Index("ix_tool_definitions_status_category_key", "status", "category", "key"),
        Index("ix_tool_definitions_risk_status", "risk_level", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(150), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class CompanyTool(Base):
    __tablename__ = "company_tools"
    __table_args__ = (
        UniqueConstraint("company_id", "tool_definition_id", name="uq_company_tools_company_tool"),
        CheckConstraint("status IN ('enabled','disabled')", name="ck_company_tools_status"),
        CheckConstraint("(status='enabled' AND enabled_at IS NOT NULL) OR status='disabled'", name="ck_company_tools_enabled_at"),
        CheckConstraint("(status='disabled' AND disabled_at IS NOT NULL) OR status='enabled'", name="ck_company_tools_disabled_at"),
        Index("ix_company_tools_company_status_tool", "company_id", "status", "tool_definition_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    tool_definition_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tool_definitions.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    enabled_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    disabled_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AgentToolGrant(Base):
    __tablename__ = "agent_tool_grants"
    __table_args__ = (
        ForeignKeyConstraint(["company_id", "agent_id"], ["agents.company_id", "agents.id"], name="fk_agent_tool_grants_company_agent", ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "tool_definition_id"], ["company_tools.company_id", "company_tools.tool_definition_id"], name="fk_agent_tool_grants_company_tool", ondelete="RESTRICT"),
        CheckConstraint("status IN ('active','revoked')", name="ck_agent_tool_grants_status"),
        CheckConstraint("(status='revoked' AND revoked_at IS NOT NULL) OR status='active'", name="ck_agent_tool_grants_revocation"),
        Index("uq_agent_tool_grants_active", "company_id", "agent_id", "tool_definition_id", unique=True, postgresql_where=text("status = 'active'")),
        Index("ix_agent_tool_grants_company_agent_status", "company_id", "agent_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    agent_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    tool_definition_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    granted_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    revoked_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
