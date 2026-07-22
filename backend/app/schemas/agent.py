"""Strict schemas for agent identity and machine authentication."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.agent import AgentCredentialStatus, AgentPermissionStatus, AgentStatus, AgentType


class AgentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    agent_type: AgentType
    description: str | None = Field(default=None, max_length=2000)
    status: Literal[AgentStatus.ACTIVE, AgentStatus.INACTIVE] = AgentStatus.ACTIVE
    is_system: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str: return value.lower()


class AgentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    agent_type: AgentType | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def require_field(self) -> "AgentUpdate":
        values = self.model_dump(exclude_unset=True)
        if not values or any(value is None for value in values.values()): raise ValueError("At least one non-null agent field is required.")
        return self


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    name: str
    slug: str
    agent_type: AgentType
    description: str | None
    status: AgentStatus
    is_system: bool
    metadata: dict[str, Any] = Field(validation_alias="metadata_")
    auth_version: int
    revoked_at: datetime | None
    revocation_reason: str | None
    created_at: datetime
    updated_at: datetime


class AgentListResponse(BaseModel):
    items: list[AgentResponse]
    total: int
    limit: int
    offset: int


class AgentReason(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=1000)


class AgentCredentialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def future_expiry(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value <= datetime.now(value.tzinfo)): raise ValueError("expires_at must be timezone-aware and in the future.")
        return value


class AgentCredentialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    agent_id: UUID
    name: str
    public_id: str
    secret_prefix: str
    secret_last_four: str
    status: AgentCredentialStatus
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    rotated_from_credential_id: UUID | None
    created_at: datetime


class AgentCredentialOneTimeResponse(AgentCredentialResponse):
    credential: str


class AgentPermissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    permission_key: str = Field(min_length=3, max_length=150, pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
    grant_reason: str | None = Field(default=None, max_length=1000)

    @field_validator("permission_key", mode="before")
    @classmethod
    def normalize_key(cls, value: str) -> str: return value.strip().lower()


class AgentPermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    agent_id: UUID
    permission_key: str
    status: AgentPermissionStatus
    grant_reason: str | None
    revocation_reason: str | None
    revoked_at: datetime | None
    created_at: datetime


class AgentTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    agent: AgentResponse
    company_id: UUID
    credential_id: UUID


class AuthenticatedAgentResponse(BaseModel):
    agent_id: UUID
    company_id: UUID
    name: str
    slug: str
    agent_type: AgentType
    status: AgentStatus
    permissions: list[str]
    credential_id: UUID
