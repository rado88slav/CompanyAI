"""Strict public schemas for the thin email workflow."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

import re
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}$")

def normalize_email(value: str) -> str:
    normalized = value.strip().casefold()
    if len(normalized) > 254 or not EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("A valid email address is required.")
    return normalized


class TestInboundEmailImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_message_id: str = Field(min_length=1, max_length=200)
    sender_name: str | None = Field(default=None, max_length=200)
    sender_email: str
    recipient_email: str
    subject: str = Field(max_length=500)
    body: str = Field(min_length=1, max_length=50_000)
    received_at: datetime

    @field_validator("external_message_id", "sender_name", "subject", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("sender_email", "recipient_email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class ReplyProposalWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient_email: str
    subject: str = Field(max_length=500)
    body: str = Field(min_length=1, max_length=50_000)

    @field_validator("subject", mode="before")
    @classmethod
    def strip_subject(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("recipient_email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class ReplyProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    inbound_email_id: UUID
    recipient_email: str
    subject: str
    body: str
    status: str
    approval_request_id: UUID | None
    created_by_administrator_id: UUID
    created_at: datetime
    updated_at: datetime


class OutboundEmailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    provider_execution_id: UUID
    status: str
    provider_message_id: str | None
    sent_at: datetime | None
    created_at: datetime


class InboundEmailSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    sender_name: str | None
    sender_email: str
    recipient_email: str
    subject: str
    received_at: datetime
    status: str
    proposal_status: str | None = None
    approval_status: str | None = None
    send_status: str | None = None


class InboundEmailDetail(InboundEmailSummary):
    external_message_id: str
    body: str
    created_at: datetime
    updated_at: datetime
    reply_proposal: ReplyProposalResponse | None = None
    outbound_email: OutboundEmailResponse | None = None


class InboundEmailListResponse(BaseModel):
    items: list[InboundEmailSummary]
    total: int
    limit: int
    offset: int


class EmailApprovalResponse(BaseModel):
    id: UUID
    status: str
    requester_administrator_id: UUID | None
    created_at: datetime
    recipient_email: str
    subject: str
    body: str
    inbound_email_id: UUID
    inbound_subject: str
    requested_action: str


class EmailApprovalListResponse(BaseModel):
    items: list[EmailApprovalResponse]
    total: int
    limit: int
    offset: int


class SendReplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_connection_id: UUID
    controlled_failure: bool = False


def _reject_multiple_recipients(value: str) -> str:
    if any(separator in value for separator in [",", ";", "\n", "\r"]):
        raise ValueError("Exactly one recipient is required.")
    return normalize_email(value)


class SingleMessageTestBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_connection_id: UUID
    recipient_email: str
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=50_000)
    idempotency_key: str = Field(min_length=12, max_length=200, pattern=r"^[a-zA-Z0-9_.:-]+$")

    @field_validator("recipient_email")
    @classmethod
    def validate_single_recipient(cls, value: str) -> str:
        return _reject_multiple_recipients(value)

    @field_validator("subject", mode="before")
    @classmethod
    def strip_single_subject(cls, value):
        return value.strip() if isinstance(value, str) else value


class SingleMessageMode(StrEnum):
    SIMULATION = "simulation"
    LIVE_TEST = "live_test"


class SingleMessagePreviewRequest(SingleMessageTestBase):
    mode: SingleMessageMode = SingleMessageMode.SIMULATION


class SingleMessageApprovalRequest(SingleMessageTestBase):
    mode: SingleMessageMode = SingleMessageMode.SIMULATION
    confirmation_text: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_confirmation(self) -> "SingleMessageApprovalRequest":
        if self.confirmation_text != "CONFIRM ONE TEST EMAIL":
            raise ValueError("Explicit confirmation is required.")
        return self


class SingleMessageSimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_execution_id: UUID
    confirmation_text: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_confirmation(self) -> "SingleMessageSimulationRequest":
        if self.confirmation_text != "CONFIRM SIMULATION ONLY":
            raise ValueError("Explicit simulation confirmation is required.")
        return self


class SingleMessageLiveExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_execution_id: UUID
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=50_000)
    confirmation_text: str = Field(min_length=1, max_length=80)

    @field_validator("subject", mode="before")
    @classmethod
    def strip_subject(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_confirmation(self) -> "SingleMessageLiveExecutionRequest":
        if self.confirmation_text != "SEND ONE TEST EMAIL":
            raise ValueError("Explicit live-send confirmation is required.")
        return self


class SingleMessagePreviewResponse(BaseModel):
    provider_connection_id: UUID
    sender_email: str
    recipient_email: str
    subject: str
    body: str
    payload_digest: str
    idempotency_key: str
    approval_required: bool
    simulation_only: bool
    live_send_available: bool
    disabled_features: list[str]
    mode: SingleMessageMode = SingleMessageMode.SIMULATION


class SingleMessageApprovalResponse(SingleMessagePreviewResponse):
    provider_execution_id: UUID
    approval_request_id: UUID
    status: str


class SingleMessageSimulationResponse(BaseModel):
    provider_execution_id: UUID
    status: str
    result_metadata: dict
    simulation_only: bool
    external_action_taken: bool


class SingleMessageLiveExecutionResponse(BaseModel):
    provider_execution_id: UUID
    status: str
    result_metadata: dict
    simulation_only: bool
    external_action_taken: bool


class SingleMessageRecipientAllowlistResponse(BaseModel):
    recipient_allowlist: list[str]
    exact_only: bool = True


class SingleMessageRecipientAllowlistUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient_email: str

    @field_validator("recipient_email")
    @classmethod
    def validate_recipient(cls, value: str) -> str:
        normalized = _reject_multiple_recipients(value)
        if "*" in normalized or normalized.startswith("@"):
            raise ValueError("Only exact recipient email addresses are allowed.")
        return normalized
