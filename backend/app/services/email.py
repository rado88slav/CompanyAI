"""Transactional service for the thin local-test email workflow."""

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import AuthorizationMode, RiskLevel
from app.core.provider_execution import LocalTestEmailAdapter, provider_operation_registry
from app.db.session import get_db_session
from app.models.administrator import Administrator
from app.models.audit_log import AuditAction
from app.models.email import EmailReplyProposal, InboundEmail, OutboundEmail
from app.models.provider_execution import ProviderExecution, ProviderExecutionAttempt
from app.repositories.approval import ApprovalRepository, AuthorizationRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.email import EmailRepository
from app.repositories.provider_connection import ProviderConnectionRepository
from app.repositories.provider_execution import ProviderExecutionRepository
from app.repositories.agent import AgentRepository
from app.schemas.approval import ApprovalDecisionCreate, ApprovalRequestCreate, AuthorizationConditionsV1
from app.schemas.email import ReplyProposalWrite, SendReplyRequest, TestInboundEmailImport
from app.services.approval_manager import ApprovalManagerService
from app.services.audit_log import AuditLogService


class EmailNotFoundError(Exception): pass
class EmailConflictError(Exception): pass
class EmailForbiddenError(Exception): pass


def content_digest(recipient: str, subject: str, body: str) -> str:
    canonical = json.dumps(
        {"body": body, "recipient_email": recipient.casefold(), "subject": subject},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def reply_subject(subject: str) -> str:
    normalized = re.sub(r"^(?:\s*re\s*:\s*)+", "", subject, flags=re.IGNORECASE).strip()
    return f"Re: {normalized}" if normalized else "Re:"


class EmailWorkflowService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = EmailRepository(session)
        self.approvals = ApprovalRepository(session)
        self.authorizations = AuthorizationRepository(session)
        self.connections = ProviderConnectionRepository(session)
        self.executions = ProviderExecutionRepository(session)
        self.audit = AuditLogService(AuditLogRepository(session))
        self.approval_service = ApprovalManagerService(self.approvals, self.authorizations, self.audit, session, AgentRepository(session))

    def _event(self, company_id: UUID, actor: Administrator, action: AuditAction, resource_type: str, resource_id: UUID, details: dict) -> None:
        self.audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=action.value, resource_type=resource_type, resource_id=resource_id, details=details)

    def import_test(self, company_id: UUID, data: TestInboundEmailImport, actor: Administrator):
        if self.repo.inbound_by_external(company_id, data.external_message_id):
            raise EmailConflictError
        item = InboundEmail(company_id=company_id, provider_connection_id=None, status="received", **data.model_dump())
        try:
            self.repo.add(item)
            self._event(company_id, actor, AuditAction.EMAIL_IMPORTED, "inbound_email", item.id, {"external_message_id": item.external_message_id, "status": item.status})
            self.session.commit()
            return item
        except IntegrityError as exc:
            self.session.rollback()
            raise EmailConflictError from exc

    def _status(self, proposal):
        if proposal is None or proposal.approval_request_id is None:
            return proposal.status if proposal else None, None
        approval = self.approvals.get_request(company_id=proposal.company_id, request_id=proposal.approval_request_id)
        if approval and approval.status == "approved" and proposal.status == "awaiting_approval":
            proposal.status = "approved"
        elif approval and approval.status == "denied" and proposal.status == "awaiting_approval":
            proposal.status = "rejected"
        return proposal.status, approval.status if approval else None

    def summary(self, item):
        proposal = self.repo.proposal_for_inbound(item.company_id, item.id)
        proposal_status, approval_status = self._status(proposal)
        outbound = self.repo.outbound_for_proposal(item.company_id, proposal.id) if proposal else None
        return {
            "id": item.id, "sender_name": item.sender_name, "sender_email": item.sender_email,
            "recipient_email": item.recipient_email, "subject": item.subject, "received_at": item.received_at,
            "status": item.status, "proposal_status": proposal_status, "approval_status": approval_status,
            "send_status": outbound.status if outbound else None,
        }

    def list(self, company_id: UUID, limit: int, offset: int):
        items = self.repo.list_inbound(company_id, limit, offset)
        return [self.summary(item) for item in items], self.repo.count_inbound(company_id)

    def detail(self, company_id: UUID, email_id: UUID):
        item = self.repo.inbound(company_id, email_id)
        if item is None: raise EmailNotFoundError
        result = self.summary(item)
        proposal = self.repo.proposal_for_inbound(company_id, email_id)
        outbound = self.repo.outbound_for_proposal(company_id, proposal.id) if proposal else None
        result.update({"external_message_id": item.external_message_id, "body": item.body, "created_at": item.created_at, "updated_at": item.updated_at, "reply_proposal": proposal, "outbound_email": outbound})
        return result

    def create_proposal(self, company_id: UUID, email_id: UUID, data: ReplyProposalWrite | None, actor: Administrator):
        inbound = self.repo.inbound(company_id, email_id, lock=True)
        if inbound is None: raise EmailNotFoundError
        if self.repo.proposal_for_inbound(company_id, email_id): raise EmailConflictError
        values = data.model_dump() if data else {"recipient_email": inbound.sender_email, "subject": reply_subject(inbound.subject), "body": "Draft reply — replace this text before requesting approval."}
        proposal = EmailReplyProposal(company_id=company_id, inbound_email_id=email_id, status="draft", content_sha256=content_digest(**{"recipient": values["recipient_email"], "subject": values["subject"], "body": values["body"]}), created_by_administrator_id=actor.id, **values)
        self.repo.add(proposal); inbound.status = "reply_drafted"
        self._event(company_id, actor, AuditAction.EMAIL_REPLY_DRAFTED, "email_reply_proposal", proposal.id, {"inbound_email_id": str(email_id), "status": proposal.status})
        self.session.commit(); return proposal

    def update_proposal(self, company_id: UUID, proposal_id: UUID, data: ReplyProposalWrite, actor: Administrator):
        proposal = self.repo.proposal(company_id, proposal_id, lock=True)
        if proposal is None: raise EmailNotFoundError
        if proposal.status != "draft" or proposal.approval_request_id is not None: raise EmailConflictError
        for key, value in data.model_dump().items(): setattr(proposal, key, value)
        proposal.content_sha256 = content_digest(proposal.recipient_email, proposal.subject, proposal.body)
        self._event(company_id, actor, AuditAction.EMAIL_REPLY_UPDATED, "email_reply_proposal", proposal.id, {"status": proposal.status})
        self.session.commit(); return proposal

    def submit(self, company_id: UUID, proposal_id: UUID, actor: Administrator):
        proposal = self.repo.proposal(company_id, proposal_id, lock=True)
        if proposal is None: raise EmailNotFoundError
        if proposal.status != "draft" or proposal.approval_request_id is not None: raise EmailConflictError
        digest = content_digest(proposal.recipient_email, proposal.subject, proposal.body)
        if digest != proposal.content_sha256: raise EmailConflictError
        request = self.approval_service.create_request(company_id=company_id, actor=actor, commit=False, payload=ApprovalRequestCreate(
            authorization_mode=AuthorizationMode.APPROVE_SINGLE_ACTION, action_type="email.reply.send",
            tool_identifier="provider.local_test_email.send_email", risk_level=RiskLevel.HIGH,
            scope_type="company", scope_id=company_id, target_resource_type="email_reply_proposal",
            target_resource_id=proposal.id, requested_conditions=AuthorizationConditionsV1(payload_schema="email_reply.v1", payload_digest=digest),
            reason="Review and approve this exact email reply.",
        ))
        proposal.approval_request_id = request.id; proposal.status = "awaiting_approval"
        inbound = self.repo.inbound(company_id, proposal.inbound_email_id, lock=True); inbound.status = "awaiting_approval"
        self._event(company_id, actor, AuditAction.EMAIL_REPLY_SUBMITTED, "email_reply_proposal", proposal.id, {"approval_request_id": str(request.id), "status": proposal.status})
        self.session.commit(); return proposal

    def list_approvals(self, company_id: UUID, limit: int, offset: int):
        requests = self.approvals.list_requests(company_id=company_id, requester_administrator_id=None, status=None, action_type="email.reply.send", tool_identifier=None, risk_level=None, campaign_id=None, limit=limit, offset=offset)
        items = []
        for request in requests:
            proposal = self.repo.proposal(company_id, request.target_resource_id) if request.target_resource_id else None
            if proposal is None: continue
            inbound = self.repo.inbound(company_id, proposal.inbound_email_id)
            items.append({"id": request.id, "status": request.status, "requester_administrator_id": request.requester_administrator_id, "created_at": request.created_at, "recipient_email": proposal.recipient_email, "subject": proposal.subject, "body": proposal.body, "inbound_email_id": inbound.id, "inbound_subject": inbound.subject, "requested_action": request.action_type})
        total = self.approvals.count_requests(company_id=company_id, requester_administrator_id=None, status=None, action_type="email.reply.send", tool_identifier=None, risk_level=None, campaign_id=None)
        return items, total

    def decide(self, company_id: UUID, request_id: UUID, actor: Administrator, actor_role: str | None, approve: bool):
        request = self.approvals.get_request(company_id=company_id, request_id=request_id)
        if request is None or request.action_type != "email.reply.send" or request.target_resource_id is None:
            raise EmailNotFoundError
        proposal = self.repo.proposal(company_id, request.target_resource_id, lock=True)
        if proposal is None or proposal.approval_request_id != request.id or proposal.status != "awaiting_approval":
            raise EmailConflictError
        try:
            if approve:
                self.approval_service.approve(company_id=company_id, request_id=request_id, actor=actor, actor_role=actor_role, payload=ApprovalDecisionCreate(), commit=False)
                proposal.status = "approved"; inbound_status = "approved"
            else:
                self.approval_service.deny(company_id=company_id, request_id=request_id, actor=actor, actor_role=actor_role, reason=None, commit=False)
                proposal.status = "rejected"; inbound_status = "rejected"
            inbound = self.repo.inbound(company_id, proposal.inbound_email_id, lock=True)
            inbound.status = inbound_status
            self.session.commit()
            return request
        except Exception:
            self.session.rollback()
            raise

    def send(self, company_id: UUID, proposal_id: UUID, data: SendReplyRequest, actor: Administrator):
        proposal = self.repo.proposal(company_id, proposal_id, lock=True)
        if proposal is None: raise EmailNotFoundError
        existing = self.repo.outbound_for_proposal(company_id, proposal_id)
        if existing is not None: return existing
        if proposal.approval_request_id is None: raise EmailForbiddenError
        approval = self.approvals.get_request(company_id=company_id, request_id=proposal.approval_request_id, for_update=True)
        digest = content_digest(proposal.recipient_email, proposal.subject, proposal.body)
        if approval is None or approval.status != "approved" or approval.target_resource_id != proposal.id or approval.requested_conditions.get("payload_digest") != digest or proposal.content_sha256 != digest:
            raise EmailForbiddenError
        connection = self.connections.connection(company_id=company_id, connection_id=data.provider_connection_id, for_update=True)
        if connection is None or connection.provider_key != "local_test_email" or connection.status != "active": raise EmailForbiddenError
        policy = self.approvals.policy_for_request(company_id=company_id, request_id=approval.id)
        if policy is None: raise EmailForbiddenError
        execution = ProviderExecution(company_id=company_id, provider_connection_id=connection.id, provider_key="local_test_email", operation_key="send_email", execution_mode="dry_run", status="running", requested_by_administrator_id=actor.id, authorization_reference=policy.id, idempotency_key=f"email-reply:{proposal.id}", request_payload={"payload_schema": "email_reply.v1", "proposal_id": str(proposal.id), "payload_digest": digest, "controlled_failure": data.controlled_failure}, result_metadata={}, started_at=datetime.now(UTC))
        self.executions.add(execution)
        attempt = ProviderExecutionAttempt(company_id=company_id, provider_execution_id=execution.id, attempt_number=1, status="running", adapter_name=LocalTestEmailAdapter.name, request_metadata={"payload_schema": "email_reply.v1"}, response_metadata={}, error_metadata={}, started_at=execution.started_at)
        self.executions.add_attempt(attempt)
        outbound = OutboundEmail(company_id=company_id, reply_proposal_id=proposal.id, provider_execution_id=execution.id, recipient_email=proposal.recipient_email, subject=proposal.subject, body=proposal.body, content_sha256=digest, status="pending")
        self.repo.add(outbound)
        self._event(company_id, actor, AuditAction.PROVIDER_EXECUTION_REQUESTED, "provider_execution", execution.id, {"provider_key": "local_test_email", "operation_key": "send_email", "execution_mode": "dry_run"})
        self._event(company_id, actor, AuditAction.PROVIDER_EXECUTION_AUTHORIZED, "provider_execution", execution.id, {"policy_id": str(policy.id), "operation_key": "send_email"})
        self._event(company_id, actor, AuditAction.PROVIDER_EXECUTION_STARTED, "provider_execution", execution.id, {"operation_key": "send_email", "attempt_number": 1})
        try:
            result = LocalTestEmailAdapter().execute(provider_operation_registry.require("local_test_email", "send_email"), {"recipient_email": proposal.recipient_email, "subject": proposal.subject, "body": proposal.body, "controlled_failure": data.controlled_failure}, idempotency_key=execution.idempotency_key)
            now = datetime.now(UTC); execution.status = "succeeded"; execution.result_metadata = result; execution.completed_at = now
            attempt.status = "succeeded"; attempt.response_metadata = {"provider_message_id": result["provider_message_id"]}; attempt.completed_at = now
            outbound.status = "sent"; outbound.provider_message_id = result["provider_message_id"]; outbound.sent_at = now
            proposal.status = "sent"; inbound = self.repo.inbound(company_id, proposal.inbound_email_id, lock=True); inbound.status = "sent"
            self._event(company_id, actor, AuditAction.PROVIDER_EXECUTION_SUCCEEDED, "provider_execution", execution.id, {"operation_key": "send_email"})
            self._event(company_id, actor, AuditAction.EMAIL_REPLY_SENT, "outbound_email", outbound.id, {"provider_execution_id": str(execution.id), "status": "sent"})
            self.session.commit(); return outbound
        except Exception as exc:
            now = datetime.now(UTC); execution.status = "failed"; execution.error_category = "provider_error"; execution.error_message = "Test delivery failed."; execution.completed_at = now
            attempt.status = "failed"; attempt.error_metadata = {"category": "provider_error"}; attempt.completed_at = now
            outbound.status = "failed"; proposal.status = "send_failed"; inbound = self.repo.inbound(company_id, proposal.inbound_email_id, lock=True); inbound.status = "send_failed"
            self._event(company_id, actor, AuditAction.PROVIDER_EXECUTION_FAILED, "provider_execution", execution.id, {"operation_key": "send_email", "category": "provider_error"})
            self._event(company_id, actor, AuditAction.EMAIL_REPLY_SEND_FAILED, "outbound_email", outbound.id, {"provider_execution_id": str(execution.id), "status": "failed"})
            self.session.commit()
            raise EmailConflictError from exc


def get_email_workflow_service(session: Annotated[Session, Depends(get_db_session)]) -> EmailWorkflowService:
    return EmailWorkflowService(session)
