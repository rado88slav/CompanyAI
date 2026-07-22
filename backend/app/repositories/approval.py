"""Company-isolated persistence for approvals and authorization."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.approval import ApprovalDecision, ApprovalRequest, AuthorizationPolicy, AuthorizationUsage


class ApprovalRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_request(self, **values: object) -> ApprovalRequest:
        item = ApprovalRequest(**values)
        self._session.add(item); self._session.flush(); self._session.refresh(item)
        return item

    def get_request(self, *, company_id: UUID, request_id: UUID, for_update: bool = False) -> ApprovalRequest | None:
        statement = select(ApprovalRequest).where(ApprovalRequest.company_id == company_id, ApprovalRequest.id == request_id)
        if for_update: statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_pending_by_dedup(self, *, company_id: UUID, deduplication_key: str) -> ApprovalRequest | None:
        return self._session.scalar(select(ApprovalRequest).where(ApprovalRequest.company_id == company_id, ApprovalRequest.deduplication_key == deduplication_key, ApprovalRequest.status == "pending"))

    def find_pending_for_action(self, *, company_id: UUID, requester_administrator_id: UUID | None, requester_agent_id: UUID | None, action_type: str, tool_identifier: str | None, scope_type: str, scope_id: UUID | None, campaign_id: UUID | None, batch_id: UUID | None) -> ApprovalRequest | None:
        return self._session.scalar(select(ApprovalRequest).where(ApprovalRequest.company_id == company_id, ApprovalRequest.status == "pending", ApprovalRequest.requester_administrator_id == requester_administrator_id, ApprovalRequest.requester_agent_id == requester_agent_id, ApprovalRequest.action_type == action_type, ApprovalRequest.tool_identifier.is_(None) if tool_identifier is None else ApprovalRequest.tool_identifier == tool_identifier, ApprovalRequest.scope_type == scope_type, ApprovalRequest.scope_id.is_(None) if scope_id is None else ApprovalRequest.scope_id == scope_id, ApprovalRequest.campaign_id.is_(None) if campaign_id is None else ApprovalRequest.campaign_id == campaign_id, ApprovalRequest.batch_id.is_(None) if batch_id is None else ApprovalRequest.batch_id == batch_id).order_by(ApprovalRequest.created_at.desc(), ApprovalRequest.id.desc()).limit(1))

    def list_requests(self, *, company_id: UUID, requester_administrator_id: UUID | None, status: str | None, action_type: str | None, tool_identifier: str | None, risk_level: str | None, campaign_id: UUID | None, limit: int, offset: int) -> list[ApprovalRequest]:
        statement = select(ApprovalRequest).where(ApprovalRequest.company_id == company_id)
        filters = ((ApprovalRequest.requester_administrator_id, requester_administrator_id), (ApprovalRequest.status, status), (ApprovalRequest.action_type, action_type), (ApprovalRequest.tool_identifier, tool_identifier), (ApprovalRequest.risk_level, risk_level), (ApprovalRequest.campaign_id, campaign_id))
        for column, value in filters:
            if value is not None: statement = statement.where(column == value)
        return list(self._session.scalars(statement.order_by(ApprovalRequest.created_at.desc(), ApprovalRequest.id.desc()).limit(limit).offset(offset)).all())

    def count_requests(self, *, company_id: UUID, requester_administrator_id: UUID | None, status: str | None, action_type: str | None, tool_identifier: str | None, risk_level: str | None, campaign_id: UUID | None) -> int:
        statement = select(func.count()).select_from(ApprovalRequest).where(ApprovalRequest.company_id == company_id)
        filters = ((ApprovalRequest.requester_administrator_id, requester_administrator_id), (ApprovalRequest.status, status), (ApprovalRequest.action_type, action_type), (ApprovalRequest.tool_identifier, tool_identifier), (ApprovalRequest.risk_level, risk_level), (ApprovalRequest.campaign_id, campaign_id))
        for column, value in filters:
            if value is not None: statement = statement.where(column == value)
        return int(self._session.scalar(statement) or 0)

    def set_request_status(self, item: ApprovalRequest, status: str) -> ApprovalRequest:
        item.status = status; self._session.flush(); self._session.refresh(item); return item

    def create_decision(self, **values: object) -> ApprovalDecision:
        item = ApprovalDecision(**values); self._session.add(item); self._session.flush(); self._session.refresh(item); return item


class AuthorizationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_policy(self, **values: object) -> AuthorizationPolicy:
        item = AuthorizationPolicy(**values); self._session.add(item); self._session.flush(); self._session.refresh(item); return item

    def get_policy(self, *, company_id: UUID, policy_id: UUID, include_platform: bool = False, for_update: bool = False) -> AuthorizationPolicy | None:
        company_filter = or_(AuthorizationPolicy.company_id == company_id, AuthorizationPolicy.policy_scope == "platform") if include_platform else AuthorizationPolicy.company_id == company_id
        statement = select(AuthorizationPolicy).where(company_filter, AuthorizationPolicy.id == policy_id)
        if for_update: statement = statement.with_for_update()
        return self._session.scalar(statement)

    def list_matching_policies(self, *, company_id: UUID) -> list[AuthorizationPolicy]:
        statement = select(AuthorizationPolicy).where(or_(AuthorizationPolicy.company_id == company_id, AuthorizationPolicy.policy_scope == "platform"), AuthorizationPolicy.status == "active")
        return list(self._session.scalars(statement).all())

    def list_policies(self, *, company_id: UUID, status: str | None, effect: str | None, action_type: str | None, tool_identifier: str | None, campaign_id: UUID | None, limit: int, offset: int) -> list[AuthorizationPolicy]:
        statement = select(AuthorizationPolicy).where(AuthorizationPolicy.company_id == company_id)
        for column, value in ((AuthorizationPolicy.status,status),(AuthorizationPolicy.effect,effect),(AuthorizationPolicy.action_type,action_type),(AuthorizationPolicy.tool_identifier,tool_identifier),(AuthorizationPolicy.campaign_id,campaign_id)):
            if value is not None: statement = statement.where(column == value)
        return list(self._session.scalars(statement.order_by(AuthorizationPolicy.created_at.desc(), AuthorizationPolicy.id.desc()).limit(limit).offset(offset)).all())

    def count_policies(self, *, company_id: UUID, status: str | None, effect: str | None, action_type: str | None, tool_identifier: str | None, campaign_id: UUID | None) -> int:
        statement = select(func.count()).select_from(AuthorizationPolicy).where(AuthorizationPolicy.company_id == company_id)
        for column, value in ((AuthorizationPolicy.status,status),(AuthorizationPolicy.effect,effect),(AuthorizationPolicy.action_type,action_type),(AuthorizationPolicy.tool_identifier,tool_identifier),(AuthorizationPolicy.campaign_id,campaign_id)):
            if value is not None: statement = statement.where(column == value)
        return int(self._session.scalar(statement) or 0)

    def revoke_policy(self, item: AuthorizationPolicy, *, actor_id: UUID, revoked_at: datetime, reason: str | None) -> AuthorizationPolicy:
        item.status="revoked"; item.revoked_at=revoked_at; item.revoked_by_administrator_id=actor_id; item.revocation_reason=reason
        self._session.flush(); self._session.refresh(item); return item

    def get_usage(self, *, company_id: UUID, usage_id: UUID) -> AuthorizationUsage | None:
        return self._session.scalar(select(AuthorizationUsage).where(AuthorizationUsage.company_id == company_id, AuthorizationUsage.id == usage_id))

    def get_usage_by_reservation(self, *, reservation_key: UUID) -> AuthorizationUsage | None:
        return self._session.scalar(select(AuthorizationUsage).where(AuthorizationUsage.reservation_key == reservation_key))

    def create_usage(self, **values: object) -> AuthorizationUsage:
        item = AuthorizationUsage(**values); self._session.add(item); self._session.flush(); self._session.refresh(item); return item

    def usage_totals(self, *, policy_id: UUID, since: datetime | None = None, target_resource_type: str | None = None, target_resource_id: UUID | None = None) -> tuple[int, Decimal]:
        statement = select(func.coalesce(func.sum(AuthorizationUsage.quantity),0), func.coalesce(func.sum(AuthorizationUsage.reserved_budget_amount),0)).where(AuthorizationUsage.authorization_policy_id == policy_id, AuthorizationUsage.status.in_(("reserved","succeeded")))
        if since is not None: statement = statement.where(AuthorizationUsage.reserved_at >= since)
        if target_resource_type is not None: statement = statement.where(AuthorizationUsage.target_resource_type == target_resource_type, AuthorizationUsage.target_resource_id == target_resource_id)
        row = self._session.execute(statement).one()
        return int(row[0]), Decimal(row[1])

    def list_usages(self, *, company_id: UUID, status: str | None, action_type: str | None, campaign_id: UUID | None, limit: int, offset: int) -> list[AuthorizationUsage]:
        statement = select(AuthorizationUsage).where(AuthorizationUsage.company_id == company_id)
        for column, value in ((AuthorizationUsage.status,status),(AuthorizationUsage.action_type,action_type),(AuthorizationUsage.campaign_id,campaign_id)):
            if value is not None: statement = statement.where(column == value)
        return list(self._session.scalars(statement.order_by(AuthorizationUsage.created_at.desc(), AuthorizationUsage.id.desc()).limit(limit).offset(offset)).all())

    def count_usages(self, *, company_id: UUID, status: str | None, action_type: str | None, campaign_id: UUID | None) -> int:
        statement = select(func.count()).select_from(AuthorizationUsage).where(AuthorizationUsage.company_id == company_id)
        for column, value in ((AuthorizationUsage.status,status),(AuthorizationUsage.action_type,action_type),(AuthorizationUsage.campaign_id,campaign_id)):
            if value is not None: statement = statement.where(column == value)
        return int(self._session.scalar(statement) or 0)

    def transition_usage(self, item: AuthorizationUsage, *, status: str, now: datetime, failure_code: str | None = None) -> AuthorizationUsage:
        item.status=status; item.failure_code=failure_code
        if status == "released": item.released_at=now
        else: item.finalized_at=now
        self._session.flush(); self._session.refresh(item); return item

    def consume_policy(self, item: AuthorizationPolicy) -> None:
        item.status="consumed"; self._session.flush()
