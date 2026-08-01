"""Normalized read-only email campaign and automation schedule schemas."""

from datetime import date, datetime, time
from enum import StrEnum
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EmailCampaignSummary(BaseModel):
    id: UUID
    company_id: UUID
    provider_key: str
    external_campaign_id: str
    name: str
    status: str
    audience_count: int
    sent_count: int
    reply_count: int
    bounce_count: int
    created_at: datetime
    updated_at: datetime


class EmailCampaignListResponse(BaseModel):
    items: list[EmailCampaignSummary]
    total: int
    limit: int
    offset: int


class MailboxRotationStrategy(StrEnum):
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    PREFERRED_WITH_FALLBACK = "preferred_with_fallback"


class ApprovalMode(StrEnum):
    DRAFT_ONLY = "draft_only"
    CAMPAIGN = "campaign"
    BATCH = "batch"
    PERIOD = "period"
    MAILBOXES = "mailboxes"
    PER_ACTION = "per_action"


class PauseReason(StrEnum):
    MANUAL = "manual"
    AUTHENTICATION_FAILURES = "authentication_failures"
    TLS_FAILURES = "tls_failures"
    CONNECTION_FAILURES = "connection_failures"
    PROVIDER_QUOTA = "provider_quota"
    HOURLY_LIMIT = "hourly_limit"
    DAILY_LIMIT = "daily_limit"
    HIGH_BOUNCE_RATE = "high_bounce_rate"
    UNSUBSCRIBE = "unsubscribe"
    NO_SUITABLE_MAILBOX = "no_suitable_mailbox"
    APPROVAL_UNAVAILABLE = "approval_unavailable"
    INTERNAL_ERROR = "internal_error"


class SendWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: time
    end: time

    @model_validator(mode="after")
    def validate_order(self) -> "SendWindow":
        if self.start >= self.end:
            raise ValueError("Send window start must be before end.")
        return self


class RandomizedTimingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_delay_minutes: int = Field(default=15, ge=1, le=1440)
    maximum_delay_minutes: int = Field(default=45, ge=1, le=1440)
    jitter_minutes: int = Field(default=10, ge=0, le=240)

    @model_validator(mode="after")
    def validate_delay_order(self) -> "RandomizedTimingSettings":
        if self.maximum_delay_minutes < self.minimum_delay_minutes:
            raise ValueError("Maximum delay must be greater than or equal to minimum delay.")
        return self


class CampaignLimitSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_hourly: int = Field(default=20, ge=1, le=500)
    campaign_daily: int = Field(default=100, ge=1, le=5000)
    mailbox_hourly: int = Field(default=10, ge=1, le=200)
    mailbox_daily: int = Field(default=40, ge=1, le=1000)
    mailbox_max_consecutive: int = Field(default=3, ge=1, le=100)
    company_daily: int | None = Field(default=None, ge=1, le=10000)

    @model_validator(mode="after")
    def validate_daily_not_lower_than_hourly(self) -> "CampaignLimitSettings":
        if self.campaign_daily < self.campaign_hourly:
            raise ValueError("Campaign daily limit must not be lower than hourly limit.")
        if self.mailbox_daily < self.mailbox_hourly:
            raise ValueError("Mailbox daily limit must not be lower than hourly limit.")
        return self


class MailboxRotationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: MailboxRotationStrategy = MailboxRotationStrategy.ROUND_ROBIN
    allowed_connection_ids: list[UUID] = Field(default_factory=list, max_length=100)
    preferred_connection_id: UUID | None = None
    reply_monitoring_required: bool = True
    paused_connection_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("allowed_connection_ids", "paused_connection_ids")
    @classmethod
    def unique_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("Connection IDs must be unique.")
        return value


class FollowUpStepSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_number: int = Field(ge=1, le=10)
    delay_amount: int = Field(ge=1, le=180)
    delay_unit: str = Field(pattern="^(calendar_days|business_days)$")
    template_reference: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_.:-]+$")
    stop_on_reply: bool = True
    stop_on_unsubscribe: bool = True
    stop_on_hard_bounce: bool = True
    stop_on_manual_block: bool = True


class AutoPauseSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authentication_failures: int = Field(default=3, ge=1, le=20)
    tls_or_connection_failures: int = Field(default=3, ge=1, le=20)
    provider_quota_reached: bool = True
    hourly_or_daily_limit_reached: bool = True
    bounce_rate_percent: float = Field(default=8.0, ge=0.0, le=100.0)
    unsubscribe_received: bool = True
    missing_mailbox: bool = True
    approval_unavailable: bool = True
    internal_error: bool = True


class CampaignScheduleSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_key: str = Field(default="default", min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    status: str = Field(default="draft", pattern="^(draft|awaiting_approval|scheduled|running|paused|completed|failed|attention_required)$")
    timezone: str = "Europe/Sofia"
    allowed_weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4], min_length=1, max_length=7)
    send_windows: list[SendWindow] = Field(default_factory=lambda: [SendWindow(start=time(9, 0), end=time(12, 0)), SendWindow(start=time(13, 30), end=time(16, 30))], min_length=1, max_length=8)
    randomized_timing: RandomizedTimingSettings = Field(default_factory=RandomizedTimingSettings)
    limits: CampaignLimitSettings = Field(default_factory=CampaignLimitSettings)
    mailbox_rotation: MailboxRotationSettings = Field(default_factory=MailboxRotationSettings)
    follow_up_steps: list[FollowUpStepSettings] = Field(default_factory=list, max_length=10)
    maximum_follow_ups: int = Field(default=3, ge=0, le=10)
    start_date: date | None = None
    end_date: date | None = None
    approval_mode: ApprovalMode = ApprovalMode.DRAFT_ONLY
    auto_pause: AutoPauseSettings = Field(default_factory=AutoPauseSettings)
    pause_reason: PauseReason | None = None
    worker_enabled: bool = False

    @field_validator("worker_enabled")
    @classmethod
    def validate_worker_disabled(cls, value: bool) -> bool:
        if value:
            raise ValueError("Campaign scheduler worker is not implemented yet.")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("A valid IANA timezone is required.") from exc
        return value

    @field_validator("allowed_weekdays")
    @classmethod
    def validate_weekdays(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("Allowed weekdays must be unique.")
        if any(item < 0 or item > 6 for item in value):
            raise ValueError("Allowed weekdays must be 0 through 6.")
        return sorted(value)

    @field_validator("send_windows")
    @classmethod
    def validate_windows(cls, value: list[SendWindow]) -> list[SendWindow]:
        ordered = sorted(value, key=lambda item: item.start)
        for previous, current in zip(ordered, ordered[1:]):
            if previous.end > current.start:
                raise ValueError("Send windows must not overlap.")
        return ordered

    @field_validator("follow_up_steps")
    @classmethod
    def validate_follow_up_steps(cls, value: list[FollowUpStepSettings]) -> list[FollowUpStepSettings]:
        numbers = [item.step_number for item in value]
        if len(numbers) != len(set(numbers)):
            raise ValueError("Follow-up step numbers must be unique.")
        return sorted(value, key=lambda item: item.step_number)

    @model_validator(mode="after")
    def validate_date_boundaries(self) -> "CampaignScheduleSettings":
        if self.end_date is not None and self.start_date is not None and self.end_date < self.start_date:
            raise ValueError("End date must not be before start date.")
        if self.maximum_follow_ups < len(self.follow_up_steps):
            raise ValueError("Maximum follow-ups must cover configured follow-up steps.")
        return self


class CampaignSchedulePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_count: int = Field(default=25, ge=1, le=50)
    include_follow_ups: bool = True


class CampaignSchedulePauseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: PauseReason = PauseReason.MANUAL


class CampaignSchedulePreviewSlot(BaseModel):
    sequence: int
    planned_at_utc: datetime | None
    planned_at_local: str | None
    timezone: str
    mailbox_connection_id: UUID | None
    mailbox_display_name: str | None
    campaign_key: str
    recipient_step: str
    status: str
    reason: str | None
    applicable_limits: dict[str, int | None]


class CampaignSchedulePreviewResponse(BaseModel):
    settings: CampaignScheduleSettings
    slots: list[CampaignSchedulePreviewSlot]
    skipped: list[CampaignSchedulePreviewSlot]
    worker_enabled: bool
    worker_contract: dict[str, str | bool]


class EmailAutomationWorkerSimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_actions: int = Field(default=10, ge=1, le=25)
    idempotency_key: str = Field(min_length=8, max_length=120, pattern=r"^[a-zA-Z0-9_.:-]+$")


class EmailAutomationWorkerSimulationResponse(BaseModel):
    simulation_only: bool
    worker_enabled: bool
    status: str
    idempotency_key: str
    would_execute: list[CampaignSchedulePreviewSlot]
    skipped: list[CampaignSchedulePreviewSlot]
    external_action_taken: bool
    provider_execution_created: bool
    audit_recorded: bool
