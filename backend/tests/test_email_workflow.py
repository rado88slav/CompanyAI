"""Focused contract and safety tests for the thin email workflow."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint

from app.core.company_permissions import CompanyPermission, role_has_permission
from app.core.provider_execution import LocalTestEmailAdapter, provider_operation_registry
from app.models.company_membership import CompanyRole
from app.models.approval import ApprovalRequest
from app.models.email import EmailReplyProposal, OutboundEmail
from app.schemas.approval import AuthorizationConditionsV1
from app.schemas.email import ReplyProposalWrite, TestInboundEmailImport as InboundImportSchema
from app.services.email import EmailSandboxRejectedError, EmailWorkflowService, content_digest, reply_subject


def test_import_schema_normalizes_email_and_rejects_unsupported_input():
    item = InboundImportSchema(external_message_id=" test-1 ", sender_name=" Sender ", sender_email=" PERSON@Example.COM ", recipient_email="Inbox@Example.com", subject=" Hello ", body="Plain text", received_at=datetime.now(UTC))
    assert (item.external_message_id, item.sender_email, item.recipient_email, item.subject) == ("test-1", "person@example.com", "inbox@example.com", "Hello")
    with pytest.raises(ValidationError):
        InboundImportSchema(external_message_id="x", sender_email="bad", recipient_email="ok@example.com", subject="", body="x", received_at=datetime.now(UTC))
    with pytest.raises(ValidationError):
        InboundImportSchema(external_message_id="x", sender_email="a@example.com", recipient_email="b@example.com", subject="", body="x", received_at=datetime.now(UTC), html="<b>x</b>")


def test_limits_and_addresses_fail_closed():
    with pytest.raises(ValidationError): ReplyProposalWrite(recipient_email="a@example.com", subject="x" * 501, body="ok")
    with pytest.raises(ValidationError): ReplyProposalWrite(recipient_email="a@example.com", subject="ok", body="x" * 50_001)
    with pytest.raises(ValidationError): ReplyProposalWrite(recipient_email="invalid", subject="ok", body="ok")


def test_reply_subject_and_exact_payload_binding():
    assert reply_subject("Question") == "Re: Question"
    assert reply_subject("RE: re: Question") == "Re: Question"
    first = content_digest("a@example.com", "Re: Question", "One")
    assert len(first) == 64
    assert first != content_digest("a@example.com", "Re: Question", "Two")
    assert first != content_digest("b@example.com", "Re: Question", "One")
    assert AuthorizationConditionsV1(payload_schema="email_reply.v1", payload_digest=first).payload_digest == first
    with pytest.raises(ValidationError): AuthorizationConditionsV1(payload_schema="email_reply.v1")


def test_local_adapter_is_deterministic_and_controlled_failure_is_sanitizable():
    descriptor = provider_operation_registry.require("local_test_email", "send_email")
    adapter = LocalTestEmailAdapter()
    payload = {"recipient_email": "a@example.com", "subject": "Hello", "body": "Text"}
    assert adapter.execute(descriptor, payload, idempotency_key="same") == adapter.execute(descriptor, payload, idempotency_key="same")
    with pytest.raises(RuntimeError, match="Controlled local test"):
        adapter.execute(descriptor, {**payload, "controlled_failure": True}, idempotency_key="failure")


def test_email_permissions_follow_role_mapping():
    assert role_has_permission(CompanyRole.VIEWER.value, CompanyPermission.EMAILS_READ)
    assert not role_has_permission(CompanyRole.VIEWER.value, CompanyPermission.EMAILS_WRITE)
    assert role_has_permission(CompanyRole.OPERATOR.value, CompanyPermission.EMAILS_WRITE)


def test_email_openapi_routes_are_registered():
    from app.main import app
    paths = app.openapi()["paths"]
    for path in ("/api/v1/companies/{company_id}/emails/test-import", "/api/v1/companies/{company_id}/emails", "/api/v1/companies/{company_id}/emails/{email_id}", "/api/v1/companies/{company_id}/emails/{email_id}/reply-proposals", "/api/v1/companies/{company_id}/reply-proposals/{proposal_id}", "/api/v1/companies/{company_id}/reply-proposals/{proposal_id}/submit", "/api/v1/companies/{company_id}/reply-proposals/{proposal_id}/send", "/api/v1/companies/{company_id}/email-approvals"):
        assert path in paths


def test_email_schema_uses_company_scoped_approval_foreign_key():
    approval_unique = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in ApprovalRequest.__table__.constraints
        if constraint.name
    }
    assert approval_unique["uq_approval_requests_company_id"] == ("company_id", "id")

    proposal_foreign_keys = {
        constraint.name: (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
            constraint.ondelete,
        )
        for constraint in EmailReplyProposal.__table__.foreign_key_constraints
    }
    assert proposal_foreign_keys["fk_email_reply_proposals_company_approval"] == (
        ("company_id", "approval_request_id"),
        ("approval_requests.company_id", "approval_requests.id"),
        "RESTRICT",
    )
    assert all(
        targets != ("approval_requests.id",)
        for _columns, targets, _ondelete in proposal_foreign_keys.values()
    )


def test_outbound_sent_state_constraint_is_fail_closed():
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in OutboundEmail.__table__.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name
    }
    sent = constraints["ck_outbound_emails_sent_result"]
    assert "status<>'sent' AND provider_message_id IS NULL AND sent_at IS NULL" in sent


def _sandbox_service(monkeypatch, *, environment: str = "local-production", policy: dict | None = None):
    from app.core.config import get_settings

    class FakeSession:
        def __init__(self):
            self.committed = False

        def scalar(self, _statement):
            return None

        def commit(self):
            self.committed = True

    class FakeRepo:
        def inbound(self, _company_id, _inbound_id, lock=False):
            return type("Inbound", (), {"recipient_email": "sender@example.test"})()

    monkeypatch.setenv("APP_ENV", environment)
    get_settings.cache_clear()
    default_policy = {
        "enabled": True,
        "recipient_allowlist": [],
        "sender_allowlist": [],
        "max_recipients_per_message": 1,
        "max_messages_per_hour": 5,
        "max_messages_per_day": 10,
        "required_subject_prefix": "[COMPANYAI TEST]",
        "emergency_stop": False,
        "attachments_enabled": False,
    }
    service = EmailWorkflowService.__new__(EmailWorkflowService)
    service.session = FakeSession()
    service.repo = FakeRepo()
    service._sandbox_policy = lambda _company_id: policy or default_policy
    service._sent_count_since = lambda _company_id, _since: 0
    service.events = []
    service._event = lambda company_id, actor, action, resource_type, resource_id, details: service.events.append(details)
    return service


def test_email_sandbox_fails_closed_without_allowlists(monkeypatch):
    from uuid import uuid4

    service = _sandbox_service(monkeypatch)
    proposal = type("Proposal", (), {"id": uuid4(), "inbound_email_id": uuid4(), "recipient_email": "allowed@example.test", "subject": "[COMPANYAI TEST] Hello", "body": "Test"})()
    actor = type("Actor", (), {"id": uuid4()})()

    with pytest.raises(EmailSandboxRejectedError):
        service._enforce_sandbox(uuid4(), proposal, actor)

    assert service.session.committed is True
    assert service.events[-1]["reason_code"] == "recipient_not_allowlisted"
    assert service.events[-1]["sandbox"] is True


def test_email_sandbox_enforces_emergency_stop_before_send(monkeypatch):
    from uuid import uuid4

    service = _sandbox_service(
        monkeypatch,
        policy={
            "enabled": True,
            "emergency_stop": True,
            "recipient_allowlist": ["allowed@example.test"],
            "sender_allowlist": ["sender@example.test"],
            "max_recipients_per_message": 1,
            "max_messages_per_hour": 5,
            "max_messages_per_day": 10,
            "required_subject_prefix": "[COMPANYAI TEST]",
            "attachments_enabled": False,
        },
    )
    proposal = type("Proposal", (), {"id": uuid4(), "inbound_email_id": uuid4(), "recipient_email": "allowed@example.test", "subject": "[COMPANYAI TEST] Hello", "body": "Test"})()
    actor = type("Actor", (), {"id": uuid4()})()

    with pytest.raises(EmailSandboxRejectedError):
        service._enforce_sandbox(uuid4(), proposal, actor)

    assert service.events[-1]["reason_code"] == "emergency_stop_enabled"


def test_development_environment_preserves_local_test_email_workflow(monkeypatch):
    from uuid import uuid4

    service = _sandbox_service(monkeypatch, environment="development")
    proposal = type("Proposal", (), {"id": uuid4(), "inbound_email_id": uuid4(), "recipient_email": "outside@example.test", "subject": "Hello", "body": "Test"})()
    actor = type("Actor", (), {"id": uuid4()})()

    service._enforce_sandbox(uuid4(), proposal, actor)

    assert service.events == []
