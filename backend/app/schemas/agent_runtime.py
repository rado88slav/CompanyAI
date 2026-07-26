"""Typed schemas for safe administrator-invoked agent runtime tools."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.tool_registry import validate_safe_tool_object, validate_tool_key


class AgentRuntimeToolResponse(BaseModel):
    key: str
    display_name: str
    description: str
    category: str
    risk_level: str
    requires_approval: bool
    runtime_registered: bool
    company_enabled: bool


class AgentRuntimeToolListResponse(BaseModel):
    items: list[AgentRuntimeToolResponse]


class AgentToolInvokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: dict[str, Any] = Field(default_factory=dict)

    @field_validator("input", mode="before")
    @classmethod
    def safe_input(cls, value: object) -> dict[str, object]:
        return validate_safe_tool_object(value, path="input")


class AgentToolInvokeResponse(BaseModel):
    tool_key: str
    status: str
    executed_at: datetime
    audit_event_id: UUID
    result: dict[str, Any]


class AgentRuntimeToolBootstrapResponse(BaseModel):
    tool_id: UUID
    company_tool_id: UUID
    tool_key: str
    company_enabled: bool
