"""Strict public schemas for Tool Registry metadata and lifecycle."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.tool_registry import validate_safe_tool_object, validate_tool_key
from app.models.tool_registry import AgentToolGrantStatus, CompanyToolStatus, ToolExecutionMode, ToolRiskLevel, ToolStatus


class ToolDefinitionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    key: str = Field(min_length=3, max_length=150)
    display_name: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    category: str = Field(min_length=1, max_length=100)
    risk_level: ToolRiskLevel
    execution_mode: ToolExecutionMode
    requires_approval: bool = False
    status: ToolStatus = ToolStatus.ACTIVE
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_system: bool = False

    @field_validator("key", mode="before")
    @classmethod
    def exact_key(cls, value: object) -> str:
        return validate_tool_key(value)  # type: ignore[arg-type]

    @field_validator("input_schema", "output_schema", "metadata", mode="before")
    @classmethod
    def safe_objects(cls, value: object, info) -> dict[str, object]:
        return validate_safe_tool_object(value, path=info.field_name)

    @model_validator(mode="after")
    def enforce_risk(self) -> "ToolDefinitionCreate":
        if self.risk_level in {ToolRiskLevel.HIGH, ToolRiskLevel.CRITICAL} and not self.requires_approval:
            raise ValueError("High and critical risk tools must require approval.")
        return self


class ToolDefinitionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    display_name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    risk_level: ToolRiskLevel | None = None
    execution_mode: ToolExecutionMode | None = None
    requires_approval: bool | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("input_schema", "output_schema", "metadata", mode="before")
    @classmethod
    def safe_objects(cls, value: object, info) -> dict[str, object] | None:
        if value is None:
            return None
        return validate_safe_tool_object(value, path=info.field_name)

    @model_validator(mode="after")
    def require_change(self) -> "ToolDefinitionUpdate":
        values = self.model_dump(exclude_unset=True)
        if not values or any(value is None for value in values.values()):
            raise ValueError("At least one non-null tool field is required.")
        risk = self.risk_level
        if risk in {ToolRiskLevel.HIGH, ToolRiskLevel.CRITICAL} and self.requires_approval is False:
            raise ValueError("High and critical risk tools must require approval.")
        return self


class ToolDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    key: str
    display_name: str
    description: str
    category: str
    risk_level: ToolRiskLevel
    execution_mode: ToolExecutionMode
    requires_approval: bool
    status: ToolStatus
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    metadata: dict[str, Any] = Field(validation_alias="metadata_")
    is_system: bool
    created_at: datetime
    updated_at: datetime


class ToolDefinitionListResponse(BaseModel):
    items: list[ToolDefinitionResponse]
    total: int
    limit: int
    offset: int


class CompanyToolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    tool_definition_id: UUID
    status: CompanyToolStatus
    enabled_at: datetime | None
    disabled_at: datetime | None
    created_at: datetime
    updated_at: datetime
    tool: ToolDefinitionResponse | None = None


class CompanyToolListResponse(BaseModel):
    items: list[CompanyToolResponse]
    total: int
    limit: int
    offset: int


class AgentToolGrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    agent_id: UUID
    tool_definition_id: UUID
    status: AgentToolGrantStatus
    granted_at: datetime
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime
    tool: ToolDefinitionResponse | None = None


class EffectiveToolResponse(BaseModel):
    tool: ToolDefinitionResponse
    grant_id: UUID
    runtime_registered: bool
    authorization_action: str


class EffectiveToolListResponse(BaseModel):
    items: list[EffectiveToolResponse]
