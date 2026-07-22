"""Internal-only deterministic authorization evaluation and reservation."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.authorization import PolicyScopeType, RISK_ORDER, RiskLevel, max_risk, resolve_platform_risk
from app.models.approval import AuthorizationPolicy, AuthorizationUsage
from app.models.audit_log import AuditAction
from app.repositories.approval import ApprovalRepository, AuthorizationRepository
from app.schemas.approval import AuthorizationAction, AuthorizationEvaluation, ReservationCreate
from app.services.audit_log import AuditLogService


class AuthorizationDeniedError(Exception): pass
class ReservationConflictError(Exception): pass
class UsageTransitionError(Exception): pass


def _actor_valid(action: AuthorizationAction) -> bool:
    return ((action.actor_type == "administrator" and action.actor_administrator_id and not action.actor_agent_id)
            or (action.actor_type == "agent" and action.actor_agent_id and not action.actor_administrator_id)
            or (action.actor_type == "system" and not action.actor_administrator_id and not action.actor_agent_id))


def _matches(policy: AuthorizationPolicy, action: AuthorizationAction, risk: RiskLevel, now: datetime) -> bool:
    if policy.status != "active" or policy.valid_from > now or (policy.expires_at and policy.expires_at <= now): return False
    if policy.subject_type != "any":
        if policy.subject_type != action.actor_type: return False
        if policy.subject_administrator_id != action.actor_administrator_id or policy.subject_agent_id != action.actor_agent_id: return False
    if policy.scope_type == PolicyScopeType.ANY.value:
        if policy.scope_id is not None: return False
    elif policy.scope_type != action.scope_type or (policy.scope_id is not None and policy.scope_id != action.scope_id):
        return False
    checks = ((policy.action_type, action.action_type), (policy.tool_identifier, action.tool_identifier), (policy.campaign_id, action.campaign_id), (policy.batch_id, action.batch_id), (policy.contact_list_id, action.contact_list_id), (policy.provider_connection_id, action.provider_connection_id))
    if any(expected is not None and expected != actual for expected, actual in checks): return False
    if policy.risk_level_max and RISK_ORDER[risk.value] > RISK_ORDER[policy.risk_level_max]: return False
    conditions = policy.conditions or {}
    scheduled = action.scheduled_for or now
    timezone_name = conditions.get("fixed_timezone") if conditions.get("timezone_policy") == "fixed" else action.timezone
    if conditions.get("timezone_policy") and not timezone_name: return False
    if timezone_name:
        try: scheduled = scheduled.astimezone(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError: return False
    if conditions.get("allowed_weekdays") and scheduled.isoweekday() not in conditions["allowed_weekdays"]: return False
    if conditions.get("allowed_local_start") and not (conditions["allowed_local_start"] <= scheduled.time().isoformat() < conditions["allowed_local_end"]): return False
    if conditions.get("allowed_recipient_countries") and action.recipient_country not in conditions["allowed_recipient_countries"]: return False
    maximum_followup = conditions.get("maximum_followup_index")
    if maximum_followup is not None and (action.followup_index is None or action.followup_index > maximum_followup): return False
    return True


def _specificity(policy: AuthorizationPolicy) -> tuple:
    exact_subject = policy.subject_type != "any"
    scope_specificity = 2 if policy.scope_id is not None else int(policy.scope_type != PolicyScopeType.ANY.value)
    selector_count = sum(value is not None for value in (policy.campaign_id, policy.batch_id, policy.contact_list_id, policy.provider_connection_id))
    exact_action = sum(value is not None for value in (policy.action_type, policy.tool_identifier))
    risk = RISK_ORDER.get(policy.risk_level_max or RiskLevel.CRITICAL.value, 99)
    expires = policy.expires_at or datetime.max.replace(tzinfo=UTC)
    capacity = policy.max_total_actions if policy.max_total_actions is not None else 2**31
    return (-int(exact_subject), -scope_specificity, -selector_count, -exact_action, risk, expires, capacity, policy.created_at, str(policy.id))


class AuthorizationEvaluatorService:
    """Not exposed through HTTP until Agent Identity exists."""

    def __init__(self, approvals: ApprovalRepository, repository: AuthorizationRepository, audit: AuditLogService, session: Session) -> None:
        self._approvals, self._repository, self._audit, self._session = approvals, repository, audit, session

    def evaluate(self, action: AuthorizationAction, *, now: datetime | None = None) -> AuthorizationEvaluation:
        if not _actor_valid(action): raise AuthorizationDeniedError("invalid_actor")
        now = now or datetime.now(UTC)
        risk = max_risk((action.risk_level or RiskLevel.LOW).value, resolve_platform_risk(action.action_type).value)
        policies = [item for item in self._repository.list_matching_policies(company_id=action.company_id) if _matches(item, action, risk, now)]
        if any(item.effect == "block" for item in policies): return AuthorizationEvaluation(status="blocked", reason_code="policy_blocked", effective_risk=risk)
        requires = [item for item in policies if item.effect == "require_approval"]
        allows = sorted((item for item in policies if item.effect == "allow"), key=_specificity)
        if requires:
            allows = [item for item in allows if item.authorization_mode == "approve_single_action" and item.source_type == "approval_decision"]
        if allows: return AuthorizationEvaluation(status="authorized", reason_code="policy_allowed", policy_id=allows[0].id, effective_risk=risk)
        pending = self._approvals.find_pending_for_action(company_id=action.company_id, requester_administrator_id=action.actor_administrator_id, requester_agent_id=action.actor_agent_id, action_type=action.action_type, tool_identifier=action.tool_identifier, scope_type=action.scope_type, scope_id=action.scope_id, campaign_id=action.campaign_id, batch_id=action.batch_id)
        if pending is not None:
            return AuthorizationEvaluation(status="pending_approval", reason_code="existing_pending_request", approval_request_id=pending.id, effective_risk=risk)
        return AuthorizationEvaluation(status="approval_required", reason_code="no_matching_grant", effective_risk=risk)

    @staticmethod
    def _compatible(existing: AuthorizationUsage, request: ReservationCreate) -> bool:
        action = request.action
        return existing.company_id == action.company_id and existing.authorization_policy_id == request.policy_id and existing.execution_id == request.execution_id and existing.actor_type == action.actor_type and existing.actor_administrator_id == action.actor_administrator_id and existing.actor_agent_id == action.actor_agent_id and existing.action_type == action.action_type and existing.quantity == action.quantity and existing.reserved_budget_amount == action.budget_amount

    def reserve(self, request: ReservationCreate) -> AuthorizationUsage:
        existing = self._repository.get_usage_by_reservation(reservation_key=request.reservation_key)
        if existing is not None:
            if not self._compatible(existing, request): raise ReservationConflictError
            return existing
        now = datetime.now(UTC)
        policy = self._repository.get_policy(company_id=request.action.company_id, policy_id=request.policy_id, include_platform=True, for_update=True)
        if policy is None or not _matches(policy, request.action, max_risk((request.action.risk_level or RiskLevel.LOW).value, resolve_platform_risk(request.action.action_type).value), now) or policy.effect != "allow": raise AuthorizationDeniedError("policy_not_available")
        if request.reservation_expires_at <= now: raise AuthorizationDeniedError("reservation_expired")
        total, budget = self._repository.usage_totals(policy_id=policy.id)
        hour_total, _ = self._repository.usage_totals(policy_id=policy.id, since=now.replace(minute=0, second=0, microsecond=0))
        day_total, _ = self._repository.usage_totals(policy_id=policy.id, since=now.replace(hour=0, minute=0, second=0, microsecond=0))
        followups, _ = self._repository.usage_totals(policy_id=policy.id, target_resource_type=request.action.target_resource_type, target_resource_id=request.action.target_resource_id) if request.action.target_resource_id else (0, Decimal("0"))
        if (policy.max_total_actions is not None and total + request.action.quantity > policy.max_total_actions) or (policy.max_hourly_actions is not None and hour_total + request.action.quantity > policy.max_hourly_actions) or (policy.max_daily_actions is not None and day_total + request.action.quantity > policy.max_daily_actions) or (policy.max_followups_per_target is not None and followups + request.action.quantity > policy.max_followups_per_target): raise AuthorizationDeniedError("quantity_limit_exceeded")
        if policy.max_budget_amount is not None and budget + request.action.budget_amount > policy.max_budget_amount: raise AuthorizationDeniedError("budget_limit_exceeded")
        if policy.budget_currency != request.action.budget_currency: raise AuthorizationDeniedError("budget_currency_mismatch")
        try:
            item = self._repository.create_usage(company_id=request.action.company_id, authorization_policy_id=policy.id, reservation_key=request.reservation_key, execution_id=request.execution_id, actor_type=request.action.actor_type, actor_administrator_id=request.action.actor_administrator_id, actor_agent_id=request.action.actor_agent_id, action_type=request.action.action_type, tool_identifier=request.action.tool_identifier, campaign_id=request.action.campaign_id, batch_id=request.action.batch_id, target_resource_type=request.action.target_resource_type, target_resource_id=request.action.target_resource_id, followup_index=request.action.followup_index, quantity=request.action.quantity, reserved_budget_amount=request.action.budget_amount, budget_currency=request.action.budget_currency, status="reserved", scheduled_for=request.action.scheduled_for, reserved_at=now, reservation_expires_at=request.reservation_expires_at)
            self._audit.append_company_event(company_id=item.company_id, actor_administrator_id=request.action.actor_administrator_id, action=AuditAction.AUTHORIZATION_USAGE_RESERVED.value, resource_type="authorization_usage", resource_id=item.id, details={"policy_id": str(policy.id), "quantity": item.quantity, "actor_type": request.action.actor_type})
            self._session.commit(); return item
        except Exception:
            self._session.rollback(); raise

    def transition(self, *, company_id: UUID, usage_id: UUID, status: str, actor_administrator_id: UUID, failure_code: str | None = None) -> AuthorizationUsage:
        item = self._repository.get_usage(company_id=company_id, usage_id=usage_id)
        if item is None: raise AuthorizationDeniedError("usage_not_found")
        if item.status != "reserved" or status not in {"succeeded", "failed", "released"}: raise UsageTransitionError
        try:
            item = self._repository.transition_usage(item, status=status, now=datetime.now(UTC), failure_code=failure_code)
            if status == "succeeded":
                policy = self._repository.get_policy(company_id=company_id, policy_id=item.authorization_policy_id, include_platform=True, for_update=True)
                if policy and policy.authorization_mode == "approve_single_action": self._repository.consume_policy(policy)
            action = {"succeeded": AuditAction.AUTHORIZATION_USAGE_SUCCEEDED, "failed": AuditAction.AUTHORIZATION_USAGE_FAILED, "released": AuditAction.AUTHORIZATION_USAGE_RELEASED}[status]
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor_administrator_id, action=action.value, resource_type="authorization_usage", resource_id=item.id, details={"failure_code": failure_code} if failure_code else {})
            self._session.commit(); return item
        except Exception:
            self._session.rollback(); raise
