"""Strict schemas for approvals, policies and authorization usage."""

from datetime import datetime, time
from decimal import Decimal
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.authorization import AuthorizationMode, PolicyScopeType, RiskLevel
from app.models.approval import ApprovalDecisionValue, ApprovalRequestStatus, AuthorizationPolicyStatus, AuthorizationUsageStatus, PolicyEffect, PolicyScope, PolicySubjectType


class AuthorizationLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_total_actions: int | None = Field(default=None, gt=0)
    max_hourly_actions: int | None = Field(default=None, gt=0)
    max_daily_actions: int | None = Field(default=None, gt=0)
    max_followups_per_target: int | None = Field(default=None, gt=0)
    max_budget_amount: Decimal | None = Field(default=None, gt=0)
    budget_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_budget(self) -> "AuthorizationLimits":
        if (self.max_budget_amount is None) != (self.budget_currency is None):
            raise ValueError("Budget amount and currency must be provided together.")
        return self


class AuthorizationConditionsV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed_weekdays: list[int] | None = None
    allowed_local_start: time | None = None
    allowed_local_end: time | None = None
    timezone_policy: Literal["recipient", "company", "fixed"] | None = None
    fixed_timezone: str | None = None
    allowed_recipient_countries: list[str] | None = None
    maximum_followup_index: int | None = Field(default=None, ge=0)

    @field_validator("allowed_weekdays")
    @classmethod
    def validate_weekdays(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and (not value or any(day < 1 or day > 7 for day in value) or len(set(value)) != len(value)):
            raise ValueError("Weekdays must be unique ISO values from 1 through 7.")
        return value

    @field_validator("allowed_recipient_countries")
    @classmethod
    def validate_countries(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and any(len(code) != 2 or not code.isupper() for code in value):
            raise ValueError("Recipient countries must be uppercase ISO alpha-2 codes.")
        return value

    @model_validator(mode="after")
    def validate_window(self) -> "AuthorizationConditionsV1":
        if (self.allowed_local_start is None) != (self.allowed_local_end is None):
            raise ValueError("Both local start and end are required.")
        if self.allowed_local_start is not None and self.allowed_local_start >= self.allowed_local_end:
            raise ValueError("Allowed local start must be before end.")
        if self.timezone_policy == "fixed":
            if self.fixed_timezone is None:
                raise ValueError("Fixed timezone is required.")
            try:
                ZoneInfo(self.fixed_timezone)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("Unknown IANA timezone.") from exc
        elif self.fixed_timezone is not None:
            raise ValueError("Fixed timezone is allowed only with fixed policy.")
        return self


class ApprovalRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authorization_mode: AuthorizationMode
    action_type: str = Field(min_length=1, max_length=100)
    tool_identifier: str | None = Field(default=None, min_length=1, max_length=150)
    risk_level: RiskLevel
    scope_type: str = Field(min_length=1, max_length=32)
    scope_id: UUID | None = None
    target_resource_type: str | None = Field(default=None, min_length=1, max_length=50)
    target_resource_id: UUID | None = None
    campaign_id: UUID | None = None
    batch_id: UUID | None = None
    contact_list_id: UUID | None = None
    provider_connection_id: UUID | None = None
    requested_limits: AuthorizationLimits = Field(default_factory=AuthorizationLimits)
    requested_conditions: AuthorizationConditionsV1 = Field(default_factory=AuthorizationConditionsV1)
    reason: str | None = Field(default=None, max_length=1000)
    decision_due_at: datetime | None = None

    @model_validator(mode="after")
    def validate_mode_selectors(self) -> "ApprovalRequestCreate":
        if self.scope_type == PolicyScopeType.ANY.value:
            raise ValueError("Approval requests require a concrete scope_type.")
        if self.authorization_mode == AuthorizationMode.APPROVE_BATCH and self.batch_id is None:
            raise ValueError("approve_batch requires batch_id.")
        if self.authorization_mode == AuthorizationMode.APPROVE_CAMPAIGN and self.campaign_id is None:
            raise ValueError("approve_campaign requires campaign_id.")
        if self.decision_due_at is not None and self.decision_due_at <= datetime.now(self.decision_due_at.tzinfo):
            raise ValueError("decision_due_at must be in the future.")
        return self


class ApprovalDecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved_mode: AuthorizationMode | None = None
    approved_limits: AuthorizationLimits = Field(default_factory=AuthorizationLimits)
    approved_conditions: AuthorizationConditionsV1 = Field(default_factory=AuthorizationConditionsV1)
    reason: str | None = Field(default=None, max_length=1000)


class ApprovalDenialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=1000)


class ApprovalRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    requester_type: str
    requester_administrator_id: UUID | None
    requester_agent_id: UUID | None
    authorization_mode: AuthorizationMode
    action_type: str
    tool_identifier: str | None
    risk_level: RiskLevel
    scope_type: str
    scope_id: UUID | None
    target_resource_type: str | None
    target_resource_id: UUID | None
    campaign_id: UUID | None
    batch_id: UUID | None
    contact_list_id: UUID | None
    provider_connection_id: UUID | None
    status: ApprovalRequestStatus
    requested_limits: dict
    requested_conditions: dict
    reason: str | None
    decision_due_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApprovalRequestListResponse(BaseModel):
    items: list[ApprovalRequestResponse]
    total: int
    limit: int
    offset: int


class ApprovalDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    approval_request_id: UUID
    approver_administrator_id: UUID
    decision: ApprovalDecisionValue
    approved_mode: AuthorizationMode | None
    approved_limits: dict
    approved_conditions: dict
    reason: str | None
    created_at: datetime


class ManualPolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    effect: PolicyEffect
    authorization_mode: AuthorizationMode
    subject_type: PolicySubjectType = PolicySubjectType.ANY
    subject_administrator_id: UUID | None = None
    subject_agent_id: UUID | None = None
    scope_type: str = Field(min_length=1, max_length=32)
    scope_id: UUID | None = None
    action_type: str | None = Field(default=None, min_length=1, max_length=100)
    tool_identifier: str | None = Field(default=None, min_length=1, max_length=150)
    campaign_id: UUID | None = None
    batch_id: UUID | None = None
    contact_list_id: UUID | None = None
    provider_connection_id: UUID | None = None
    risk_level_max: RiskLevel | None = None
    limits: AuthorizationLimits = Field(default_factory=AuthorizationLimits)
    valid_from: datetime
    conditions: AuthorizationConditionsV1 = Field(default_factory=AuthorizationConditionsV1)

    @model_validator(mode="after")
    def validate_policy(self) -> "ManualPolicyCreate":
        if self.scope_type == PolicyScopeType.ANY.value and self.scope_id is not None:
            raise ValueError("Wildcard policy scope requires scope_id to be null.")
        expected = {
            AuthorizationMode.BLOCK: PolicyEffect.BLOCK,
            AuthorizationMode.ASK_EVERY_TIME: PolicyEffect.REQUIRE_APPROVAL,
            AuthorizationMode.ALWAYS_REQUIRE_APPROVAL: PolicyEffect.REQUIRE_APPROVAL,
        }
        if self.authorization_mode in expected and self.effect != expected[self.authorization_mode]:
            raise ValueError("Authorization mode and effect are incompatible.")
        if self.effect == PolicyEffect.ALLOW and self.authorization_mode in {AuthorizationMode.BLOCK, AuthorizationMode.ASK_EVERY_TIME, AuthorizationMode.ALWAYS_REQUIRE_APPROVAL}:
            raise ValueError("Authorization mode and effect are incompatible.")
        if self.authorization_mode == AuthorizationMode.APPROVE_BATCH and self.batch_id is None:
            raise ValueError("approve_batch requires batch_id.")
        if self.authorization_mode == AuthorizationMode.APPROVE_CAMPAIGN and self.campaign_id is None:
            raise ValueError("approve_campaign requires campaign_id.")
        if self.authorization_mode == AuthorizationMode.APPROVE_UNTIL and self.limits.expires_at is None:
            raise ValueError("approve_until requires expires_at.")
        if self.authorization_mode == AuthorizationMode.ALLOW_WITHIN_LIMITS and not self.limits.model_dump(exclude_none=True):
            raise ValueError("allow_within_limits requires a limit.")
        return self


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    policy_scope: PolicyScope
    company_id: UUID | None
    effect: PolicyEffect
    authorization_mode: AuthorizationMode
    source_type: str
    subject_type: PolicySubjectType
    subject_administrator_id: UUID | None
    subject_agent_id: UUID | None
    scope_type: str
    scope_id: UUID | None
    action_type: str | None
    tool_identifier: str | None
    campaign_id: UUID | None
    batch_id: UUID | None
    contact_list_id: UUID | None
    provider_connection_id: UUID | None
    risk_level_max: RiskLevel | None
    status: AuthorizationPolicyStatus
    max_total_actions: int | None
    max_hourly_actions: int | None
    max_daily_actions: int | None
    max_followups_per_target: int | None
    max_budget_amount: Decimal | None
    budget_currency: str | None
    valid_from: datetime
    expires_at: datetime | None
    conditions_schema_version: int
    conditions: dict
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PolicyListResponse(BaseModel):
    items: list[PolicyResponse]
    total: int
    limit: int
    offset: int


class AuthorizationAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_id: UUID
    actor_type: Literal["administrator", "agent", "system"]
    actor_administrator_id: UUID | None = None
    actor_agent_id: UUID | None = None
    action_type: str = Field(min_length=1, max_length=100)
    tool_identifier: str | None = None
    risk_level: RiskLevel | None = None
    scope_type: str
    scope_id: UUID | None = None
    target_resource_type: str | None = None
    target_resource_id: UUID | None = None
    campaign_id: UUID | None = None
    batch_id: UUID | None = None
    contact_list_id: UUID | None = None
    provider_connection_id: UUID | None = None
    followup_index: int | None = Field(default=None, ge=0)
    quantity: int = Field(default=1, gt=0)
    budget_amount: Decimal = Field(default=Decimal("0"), ge=0)
    budget_currency: str | None = None
    scheduled_for: datetime | None = None
    timezone: str | None = None
    recipient_country: str | None = None

    @model_validator(mode="after")
    def validate_actor_and_budget(self) -> "AuthorizationAction":
        if not self.scope_type.strip() or self.scope_type == PolicyScopeType.ANY.value:
            raise ValueError("Runtime actions require a concrete scope_type.")
        valid = ((self.actor_type == "administrator" and self.actor_administrator_id is not None and self.actor_agent_id is None)
                 or (self.actor_type == "agent" and self.actor_agent_id is not None and self.actor_administrator_id is None)
                 or (self.actor_type == "system" and self.actor_administrator_id is None and self.actor_agent_id is None))
        if not valid: raise ValueError("Actor type and identifier are inconsistent.")
        if (self.budget_amount > 0) != (self.budget_currency is not None): raise ValueError("Budget amount and currency must be provided together.")
        return self


class AuthorizationEvaluation(BaseModel):
    status: Literal["authorized", "blocked", "approval_required", "pending_approval", "limit_exceeded"]
    reason_code: str
    policy_id: UUID | None = None
    approval_request_id: UUID | None = None
    effective_risk: RiskLevel


class ReservationCreate(BaseModel):
    action: AuthorizationAction
    policy_id: UUID
    reservation_key: UUID
    execution_id: UUID | None = None
    reservation_expires_at: datetime


class UsageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    authorization_policy_id: UUID
    reservation_key: UUID
    execution_id: UUID | None
    action_type: str
    status: AuthorizationUsageStatus
    quantity: int
    reserved_budget_amount: Decimal
    reserved_at: datetime
    reservation_expires_at: datetime
    finalized_at: datetime | None
    released_at: datetime | None


class UsageListResponse(BaseModel):
    items: list[UsageResponse]
    total: int
    limit: int
    offset: int


class UsageFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    failure_code: str = Field(min_length=1, max_length=100)
