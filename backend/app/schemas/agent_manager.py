"""Schemas for the safe preview-only Agent Manager."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


AgentTaskKey = Literal[
    "preview_next_email_actions",
    "draft_interested_follow_up",
    "classify_unsubscribe",
    "propose_campaign_pause",
    "attempt_forbidden_send",
]


SAFE_EMAIL_PREVIEW_TEMPLATE_ID = "email_operations_preview_agent"


class AgentManagerTemplateResponse(BaseModel):
    template_id: str
    name: str
    role: str
    runtime_type: str
    approval_mode: str
    allowed_tools: list[str]
    forbidden_actions: list[str]
    default_permissions: list[str]


class AgentManagerAgentResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    slug: str
    role: str
    status: str
    runtime_type: str
    assigned_tools: list[str]
    permissions: list[str]
    approval_mode: str
    health: str
    readiness: str
    last_activity_at: datetime | None
    instructions: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AgentManagerListResponse(BaseModel):
    items: list[AgentManagerAgentResponse]
    total: int
    limit: int
    offset: int


class AgentManagerCreateFromTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    template_id: str = SAFE_EMAIL_PREVIEW_TEMPLATE_ID
    name: str | None = Field(default=None, min_length=2, max_length=200)
    company_instructions: str = Field(default="Use conservative, preview-only recommendations.", max_length=2000)

    @field_validator("company_instructions")
    @classmethod
    def reject_secret_like_instructions(cls, value: str) -> str:
        return _reject_secret_like(value)


class AgentManagerInstructionsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    company_instructions: str = Field(min_length=1, max_length=2000)

    @field_validator("company_instructions")
    @classmethod
    def reject_secret_like_instructions(cls, value: str) -> str:
        return _reject_secret_like(value)


class AgentPromptPreviewResponse(BaseModel):
    agent_id: UUID
    template_id: str
    sections: dict[str, Any]
    prompt_text: str


class AgentPreviewTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    task_key: AgentTaskKey
    synthetic_reply: str | None = Field(default=None, max_length=2000)

    @field_validator("synthetic_reply")
    @classmethod
    def reject_secret_like_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _reject_secret_like(value)


def _reject_secret_like(value: str) -> str:
    lowered = value.lower()
    if any(part in lowered for part in ("password", "api_key", "access token", "private key", "credential")):
        raise ValueError("Input must not contain secret-like values.")
    return value


class AgentProposalResponse(BaseModel):
    proposal_type: str
    summary: str
    recommended_action: str
    draft_subject: str | None = None
    draft_body: str | None = None
    classification: str | None = None
    safety_notes: list[str]


class AgentAuthorizationResult(BaseModel):
    status: str
    reason_code: str
    effective_risk: str
    approval_request_id: UUID | None = None
    policy_id: UUID | None = None


class AgentPreviewTaskResponse(BaseModel):
    agent_id: UUID
    task_key: str
    runtime_type: str
    status: str
    proposal: AgentProposalResponse
    authorization: AgentAuthorizationResult
    audit_event_id: UUID
    provider_execution_created: bool = False
    external_action_taken: bool = False
