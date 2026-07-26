"""Transactional human approval and policy management."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.authorization import RISK_ORDER, RiskLevel, max_risk, resolve_platform_risk
from app.db.session import get_db_session
from app.models.administrator import Administrator
from app.models.approval import ApprovalRequest, AuthorizationPolicy, AuthorizationUsage
from app.models.audit_log import AuditAction
from app.models.company_membership import CompanyRole
from app.repositories.approval import ApprovalRepository, AuthorizationRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.agent import AgentRepository
from app.schemas.approval import ApprovalDecisionCreate, ApprovalRequestCreate, ManualPolicyCreate
from app.services.audit_log import AuditLogService


class ApprovalNotFoundError(Exception): pass
class ApprovalConflictError(Exception): pass
class ApprovalForbiddenError(Exception): pass
class ApprovalValidationError(Exception): pass


def _json(value: object) -> dict:
    return value.model_dump(mode="json", exclude_none=True)  # type: ignore[union-attr]


def _dedup(company_id: UUID, actor_id: UUID, payload: ApprovalRequestCreate) -> str:
    selectors = {
        "company_id": str(company_id), "actor_id": str(actor_id),
        "authorization_mode": payload.authorization_mode.value,
        "action_type": payload.action_type, "tool_identifier": payload.tool_identifier,
        "scope_type": payload.scope_type, "scope_id": str(payload.scope_id) if payload.scope_id else None,
        "target_resource_type": payload.target_resource_type,
        "target_resource_id": str(payload.target_resource_id) if payload.target_resource_id else None,
        "campaign_id": str(payload.campaign_id) if payload.campaign_id else None,
        "batch_id": str(payload.batch_id) if payload.batch_id else None,
        "contact_list_id": str(payload.contact_list_id) if payload.contact_list_id else None,
        "provider_connection_id": str(payload.provider_connection_id) if payload.provider_connection_id else None,
    }
    canonical = json.dumps(selectors, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class ApprovalManagerService:
    def __init__(self, approvals: ApprovalRepository, authorizations: AuthorizationRepository, audit: AuditLogService, session: Session, agents: AgentRepository | None = None) -> None:
        self._approvals, self._authorizations, self._audit, self._session, self._agents = approvals, authorizations, audit, session, agents

    def _atomic(self, operation):
        try:
            result = operation(); self._session.commit(); return result
        except Exception:
            self._session.rollback(); raise

    def create_request(self, *, company_id: UUID, actor: Administrator, payload: ApprovalRequestCreate, commit: bool = True) -> ApprovalRequest:
        key = _dedup(company_id, actor.id, payload)
        existing = self._approvals.get_pending_by_dedup(company_id=company_id, deduplication_key=key)
        if existing is not None: return existing
        effective = max_risk(payload.risk_level.value, resolve_platform_risk(payload.action_type).value)
        def operation():
            item = self._approvals.create_request(company_id=company_id, requester_type="administrator", requester_administrator_id=actor.id, requester_agent_id=None, authorization_mode=payload.authorization_mode.value, action_type=payload.action_type, tool_identifier=payload.tool_identifier, risk_level=effective.value, scope_type=payload.scope_type, scope_id=payload.scope_id, target_resource_type=payload.target_resource_type, target_resource_id=payload.target_resource_id, campaign_id=payload.campaign_id, batch_id=payload.batch_id, contact_list_id=payload.contact_list_id, provider_connection_id=payload.provider_connection_id, requested_limits=_json(payload.requested_limits), requested_conditions=_json(payload.requested_conditions), reason=payload.reason, deduplication_key=key, decision_due_at=payload.decision_due_at)
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.APPROVAL_REQUEST_CREATED.value, resource_type="approval_request", resource_id=item.id, details={"action_type": item.action_type, "risk_level": item.risk_level, "approval_mode": item.authorization_mode})
            return item
        return self._atomic(operation) if commit else operation()

    def _expire(self, item: ApprovalRequest, *, actor_id: UUID) -> ApprovalRequest:
        now = datetime.now(UTC)
        if item.status == "pending" and item.decision_due_at and item.decision_due_at <= now:
            def operation():
                self._approvals.set_request_status(item, "expired")
                self._audit.append_company_event(company_id=item.company_id, actor_administrator_id=actor_id, action=AuditAction.APPROVAL_REQUEST_EXPIRED.value, resource_type="approval_request", resource_id=item.id, details={"reason_code": "decision_due_elapsed"})
                return item
            return self._atomic(operation)
        return item

    def get_request(self, *, company_id: UUID, request_id: UUID, actor: Administrator, own_only: bool = False) -> ApprovalRequest:
        item = self._approvals.get_request(company_id=company_id, request_id=request_id)
        if item is None or (own_only and item.requester_administrator_id != actor.id): raise ApprovalNotFoundError
        return self._expire(item, actor_id=actor.id)

    def list_requests(self, *, company_id: UUID, actor: Administrator, own_only: bool, requester_administrator_id: UUID | None, status: str | None, action_type: str | None, tool_identifier: str | None, risk_level: str | None, campaign_id: UUID | None, limit: int, offset: int) -> tuple[list[ApprovalRequest], int]:
        if own_only:
            requester_administrator_id = actor.id
        filters = {
            "company_id": company_id,
            "requester_administrator_id": requester_administrator_id,
            "status": status,
            "action_type": action_type,
            "tool_identifier": tool_identifier,
            "risk_level": risk_level,
            "campaign_id": campaign_id,
        }
        items = self._approvals.list_requests(**filters, limit=limit, offset=offset)
        total = self._approvals.count_requests(**filters)
        return items, total

    def _may_decide(self, *, role: str | None, superuser: bool, request: ApprovalRequest, reusable: bool) -> bool:
        if superuser or role == CompanyRole.OWNER.value: return True
        return role == CompanyRole.ADMIN.value and RISK_ORDER[request.risk_level] <= RISK_ORDER[RiskLevel.MEDIUM.value] and not reusable

    @staticmethod
    def _validate_narrowing(request: ApprovalRequest, payload: ApprovalDecisionCreate) -> None:
        requested = request.requested_limits
        approved = _json(payload.approved_limits)
        for key in ("max_total_actions", "max_hourly_actions", "max_daily_actions", "max_followups_per_target", "max_budget_amount"):
            if approved.get(key) is not None and (requested.get(key) is None or float(approved[key]) > float(requested[key])):
                raise ApprovalValidationError
        if approved.get("expires_at") and requested.get("expires_at") and approved["expires_at"] > requested["expires_at"]:
            raise ApprovalValidationError

    def approve(self, *, company_id: UUID, request_id: UUID, actor: Administrator, actor_role: str | None, payload: ApprovalDecisionCreate, commit: bool = True):
        request = self._approvals.get_request(company_id=company_id, request_id=request_id, for_update=True)
        if request is None: raise ApprovalNotFoundError
        if request.status != "pending": raise ApprovalConflictError
        if request.requester_administrator_id == actor.id: raise ApprovalForbiddenError
        mode = (payload.approved_mode or request.authorization_mode)
        mode_value = mode.value if hasattr(mode, "value") else mode
        reusable = mode_value not in {"approve_single_action", "ask_every_time"}
        if not self._may_decide(role=actor_role, superuser=actor.is_superuser, request=request, reusable=reusable): raise ApprovalForbiddenError
        self._validate_narrowing(request, payload)
        def operation():
            decision = self._approvals.create_decision(company_id=company_id, approval_request_id=request.id, approver_administrator_id=actor.id, decision="approved", approved_mode=mode_value, approved_limits=_json(payload.approved_limits), approved_conditions=_json(payload.approved_conditions), reason=payload.reason)
            limits = _json(payload.approved_limits)
            policy = self._authorizations.create_policy(policy_scope="company", company_id=company_id, effect="allow", authorization_mode=mode_value, source_type="approval_decision", source_approval_request_id=request.id, source_approval_decision_id=decision.id, created_by_administrator_id=actor.id, subject_type=request.requester_type, subject_administrator_id=request.requester_administrator_id, subject_agent_id=request.requester_agent_id, scope_type=request.scope_type, scope_id=request.scope_id, action_type=request.action_type, tool_identifier=request.tool_identifier, campaign_id=request.campaign_id, batch_id=request.batch_id, contact_list_id=request.contact_list_id, provider_connection_id=request.provider_connection_id, risk_level_max=request.risk_level, status="active", max_total_actions=1 if mode_value == "approve_single_action" else limits.get("max_total_actions"), max_hourly_actions=limits.get("max_hourly_actions"), max_daily_actions=limits.get("max_daily_actions"), max_followups_per_target=limits.get("max_followups_per_target"), max_budget_amount=limits.get("max_budget_amount"), budget_currency=limits.get("budget_currency"), valid_from=datetime.now(UTC), expires_at=limits.get("expires_at"), conditions_schema_version=1, conditions=_json(payload.approved_conditions))
            self._approvals.set_request_status(request, "approved")
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.APPROVAL_REQUEST_APPROVED.value, resource_type="approval_request", resource_id=request.id, details={"decision_id": str(decision.id), "policy_id": str(policy.id), "approval_mode": mode_value})
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.AUTHORIZATION_POLICY_CREATED.value, resource_type="authorization_policy", resource_id=policy.id, details={"source_type": "approval_decision", "effect": "allow"})
            return request
        return self._atomic(operation) if commit else operation()

    def deny(self, *, company_id: UUID, request_id: UUID, actor: Administrator, actor_role: str | None, reason: str | None, commit: bool = True):
        request = self._approvals.get_request(company_id=company_id, request_id=request_id, for_update=True)
        if request is None: raise ApprovalNotFoundError
        if request.status != "pending": raise ApprovalConflictError
        if request.requester_administrator_id == actor.id or not self._may_decide(role=actor_role, superuser=actor.is_superuser, request=request, reusable=False): raise ApprovalForbiddenError
        def operation():
            self._approvals.create_decision(company_id=company_id, approval_request_id=request.id, approver_administrator_id=actor.id, decision="denied", approved_mode=None, approved_limits={}, approved_conditions={}, reason=reason)
            self._approvals.set_request_status(request, "denied")
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.APPROVAL_REQUEST_DENIED.value, resource_type="approval_request", resource_id=request.id, details={"reason_code": "administrator_denied"})
            return request
        return self._atomic(operation) if commit else operation()

    def cancel(self, *, company_id: UUID, request_id: UUID, actor: Administrator, may_cancel_any: bool):
        request = self._approvals.get_request(company_id=company_id, request_id=request_id, for_update=True)
        if request is None: raise ApprovalNotFoundError
        if request.status != "pending": raise ApprovalConflictError
        if not may_cancel_any and request.requester_administrator_id != actor.id: raise ApprovalForbiddenError
        def operation():
            self._approvals.set_request_status(request, "cancelled")
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.APPROVAL_REQUEST_CANCELLED.value, resource_type="approval_request", resource_id=request.id, details={"reason_code": "administrator_cancelled"})
            return request
        return self._atomic(operation)

    def create_manual_policy(self, *, company_id: UUID, actor: Administrator, actor_role: str | None, payload: ManualPolicyCreate) -> AuthorizationPolicy:
        risk = payload.risk_level_max or RiskLevel.HIGH
        if not actor.is_superuser and actor_role not in {CompanyRole.OWNER.value, CompanyRole.ADMIN.value}: raise ApprovalForbiddenError
        if actor_role == CompanyRole.ADMIN.value and (RISK_ORDER[risk.value] > RISK_ORDER[RiskLevel.MEDIUM.value] or payload.effect.value != "allow"): raise ApprovalForbiddenError
        if payload.subject_agent_id is not None and (self._agents is None or self._agents.get_agent(company_id=company_id, agent_id=payload.subject_agent_id) is None): raise ApprovalNotFoundError
        limits = _json(payload.limits)
        def operation():
            item = self._authorizations.create_policy(policy_scope="company", company_id=company_id, effect=payload.effect.value, authorization_mode=payload.authorization_mode.value, source_type="manual", source_approval_request_id=None, source_approval_decision_id=None, created_by_administrator_id=actor.id, subject_type=payload.subject_type.value, subject_administrator_id=payload.subject_administrator_id, subject_agent_id=payload.subject_agent_id, scope_type=payload.scope_type, scope_id=payload.scope_id, action_type=payload.action_type, tool_identifier=payload.tool_identifier, campaign_id=payload.campaign_id, batch_id=payload.batch_id, contact_list_id=payload.contact_list_id, provider_connection_id=payload.provider_connection_id, risk_level_max=risk.value, status="active", max_total_actions=limits.get("max_total_actions"), max_hourly_actions=limits.get("max_hourly_actions"), max_daily_actions=limits.get("max_daily_actions"), max_followups_per_target=limits.get("max_followups_per_target"), max_budget_amount=limits.get("max_budget_amount"), budget_currency=limits.get("budget_currency"), valid_from=payload.valid_from, expires_at=limits.get("expires_at"), conditions_schema_version=1, conditions=_json(payload.conditions))
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.AUTHORIZATION_POLICY_CREATED.value, resource_type="authorization_policy", resource_id=item.id, details={"source_type": "manual", "effect": item.effect, "risk_level_max": item.risk_level_max})
            return item
        return self._atomic(operation)

    def get_policy(self, *, company_id: UUID, policy_id: UUID):
        item = self._authorizations.get_policy(company_id=company_id, policy_id=policy_id)
        if item is None: raise ApprovalNotFoundError
        return item

    def list_policies(self, *, company_id: UUID, status: str | None, effect: str | None, action_type: str | None, tool_identifier: str | None, campaign_id: UUID | None, limit: int, offset: int) -> tuple[list[AuthorizationPolicy], int]:
        filters = {
            "company_id": company_id,
            "status": status,
            "effect": effect,
            "action_type": action_type,
            "tool_identifier": tool_identifier,
            "campaign_id": campaign_id,
        }
        items = self._authorizations.list_policies(**filters, limit=limit, offset=offset)
        total = self._authorizations.count_policies(**filters)
        return items, total

    def list_usages(self, *, company_id: UUID, status: str | None, action_type: str | None, campaign_id: UUID | None, limit: int, offset: int) -> tuple[list[AuthorizationUsage], int]:
        filters = {
            "company_id": company_id,
            "status": status,
            "action_type": action_type,
            "campaign_id": campaign_id,
        }
        items = self._authorizations.list_usages(**filters, limit=limit, offset=offset)
        total = self._authorizations.count_usages(**filters)
        return items, total
    def get_usage(self, *, company_id: UUID, usage_id: UUID):
        item = self._authorizations.get_usage(company_id=company_id, usage_id=usage_id)
        if item is None: raise ApprovalNotFoundError
        return item

    def revoke_policy(self, *, company_id: UUID, policy_id: UUID, actor: Administrator, reason: str | None):
        item = self.get_policy(company_id=company_id, policy_id=policy_id)
        if item.status != "active": raise ApprovalConflictError
        def operation():
            self._authorizations.revoke_policy(item, actor_id=actor.id, revoked_at=datetime.now(UTC), reason=reason)
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.AUTHORIZATION_POLICY_REVOKED.value, resource_type="authorization_policy", resource_id=item.id, details={"reason_code": "administrator_revoked"})
            return item
        return self._atomic(operation)


def get_approval_manager_service(session: Annotated[Session, Depends(get_db_session)]) -> ApprovalManagerService:
    return ApprovalManagerService(ApprovalRepository(session), AuthorizationRepository(session), AuditLogService(AuditLogRepository(session)), session, AgentRepository(session))
