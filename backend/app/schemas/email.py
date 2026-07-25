"""Strict public schemas for the thin email workflow."""

from datetime import datetime
from uuid import UUID

import re
from pydantic import BaseModel, ConfigDict, Field, field_validator

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
