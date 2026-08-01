"""Focused contract and safety tests for the thin email workflow."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint

from app.core.company_permissions import CompanyPermission, role_has_permission
from app.core.provider_execution import LocalTestEmailAdapter, provider_operation_registry
from app.models.company_membership import CompanyRole
from app.models.approval import ApprovalRequest
from app.models.email import EmailReplyProposal, OutboundEmail
from app.schemas.approval import AuthorizationConditionsV1
from app.schemas.email import ReplyProposalWrite, SingleMessageApprovalRequest, SingleMessagePreviewRequest, SingleMessageSimulationRequest, TestInboundEmailImport as InboundImportSchema
from app.services.email import EmailSandboxRejectedError, EmailWorkflowService, content_digest, reply_subject
from app.services.generic_smtp_imap import GENERIC_MAILBOX_HEALTH_KEY


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


class FakeAudit:
    def __init__(self):
        self.events = []

    def append_company_event(self, **kwargs):
        self.events.append(kwargs)


class FakeSingleMessageConnections:
    def __init__(self, *, connection=None, credential=None):
        self._connection = connection
        self._credential = credential

    def connection(self, *, company_id, connection_id, for_update=False):
        return self._connection if self._connection and self._connection.company_id == company_id and self._connection.id == connection_id else None

    def active_credential(self, *, company_id, connection_id, for_update=False):
        return self._credential if self._credential and self._credential.company_id == company_id and self._credential.provider_connection_id == connection_id else None


class FakeExecutions:
    def __init__(self, existing=None):
        self.existing = existing
        self.items = {}
        self.attempts = []

    def by_key(self, company_id, key):
        if self.existing and self.existing.company_id == company_id and self.existing.idempotency_key == key:
            return self.existing
        return None

    def get(self, company_id, execution_id, lock=False):
        item = self.items.get(execution_id)
        return item if item and item.company_id == company_id else None

    def add(self, item):
        if item.id is None:
            item.id = uuid4()
        self.items[item.id] = item
        return item

    def add_attempt(self, item):
        self.attempts.append(item)
        return item


class FakeApprovalService:
    def __init__(self, approval_id):
        self.approval_id = approval_id
        self.requests = []

    def create_request(self, *, company_id, actor, commit, payload):
        self.requests.append(payload)
        return SimpleNamespace(id=self.approval_id)


class FakeAuthorizer:
    def __init__(self, *, status="approval_required"):
        self.status = status
        self.reserved = False
        self.transitioned = False

    def evaluate(self, action):
        return SimpleNamespace(status=self.status, policy_id=uuid4() if self.status == "authorized" else None)

    def reserve(self, request, *, commit=False):
        self.reserved = True
        return SimpleNamespace(id=uuid4())

    def transition(self, *, company_id, usage_id, status, actor_administrator_id, commit=False):
        self.transitioned = True


def _single_message_service(monkeypatch, *, connection=None, credential=None, existing=None, policy=None, sent_count=0):
    from app.core.config import get_settings

    monkeypatch.setenv("APP_ENV", "local-production")
    get_settings.cache_clear()
    service = EmailWorkflowService.__new__(EmailWorkflowService)
    service.session = SimpleNamespace(commit=lambda: None, rollback=lambda: None)
    service.audit = FakeAudit()
    service.connections = FakeSingleMessageConnections(connection=connection, credential=credential)
    service.executions = FakeExecutions(existing=existing)
    service.approval_service = FakeApprovalService(uuid4())
    service.approvals = SimpleNamespace()
    service.authorizations = SimpleNamespace()
    service._sandbox_policy = lambda _company_id: policy or {
        "enabled": True,
        "recipient_allowlist": ["allowed@example.test"],
        "sender_allowlist": ["sender@example.test"],
        "max_recipients_per_message": 1,
        "max_messages_per_hour": 1,
        "max_messages_per_day": 1,
        "required_subject_prefix": "[COMPANYAI TEST]",
        "emergency_stop": False,
    }
    service._sent_count_since = lambda _company_id, _since: sent_count
    return service


def _active_mailbox(company_id, connection_id):
    return SimpleNamespace(
        id=connection_id,
        company_id=company_id,
        provider_key="generic_smtp_imap",
        status="active",
        configuration={"email_address": "sender@example.test"},
        metadata_={GENERIC_MAILBOX_HEALTH_KEY: {"smtp": {"status": "succeeded"}, "imap": {"status": "succeeded"}}},
    )


def _credential(company_id, connection_id):
    return SimpleNamespace(company_id=company_id, provider_connection_id=connection_id, expires_at=datetime.now(UTC) + timedelta(days=1))


def _single_message_payload(connection_id):
    return SingleMessagePreviewRequest(
        provider_connection_id=connection_id,
        recipient_email="allowed@example.test",
        subject="[COMPANYAI TEST] Controlled hello",
        body="One controlled message body.",
        idempotency_key="single-test-001",
    )


def test_single_message_preview_rejects_untested_mailbox(monkeypatch):
    company_id, connection_id = uuid4(), uuid4()
    mailbox = _active_mailbox(company_id, connection_id)
    mailbox.metadata_ = {GENERIC_MAILBOX_HEALTH_KEY: {"smtp": {"status": "failed"}, "imap": {"status": "succeeded"}}}
    service = _single_message_service(monkeypatch, connection=mailbox, credential=_credential(company_id, connection_id))

    with pytest.raises(EmailSandboxRejectedError):
        service.preview_single_message(company_id=company_id, data=_single_message_payload(connection_id), actor=SimpleNamespace(id=uuid4()))

    assert service.audit.events[-1]["details"]["reason_code"] == "smtp_not_tested"


def test_single_message_schema_rejects_multiple_recipients():
    with pytest.raises(ValidationError):
        SingleMessagePreviewRequest(provider_connection_id=uuid4(), recipient_email="a@example.test,b@example.test", subject="[COMPANYAI TEST] x", body="body", idempotency_key="single-test-002")


def test_single_message_preview_rejects_non_allowlisted_recipient(monkeypatch):
    company_id, connection_id = uuid4(), uuid4()
    service = _single_message_service(monkeypatch, connection=_active_mailbox(company_id, connection_id), credential=_credential(company_id, connection_id))
    payload = _single_message_payload(connection_id).model_copy(update={"recipient_email": "blocked@example.test"})

    with pytest.raises(EmailSandboxRejectedError):
        service.preview_single_message(company_id=company_id, data=payload, actor=SimpleNamespace(id=uuid4()))

    assert service.audit.events[-1]["details"]["reason_code"] == "recipient_not_allowlisted"


def test_single_message_preview_rejects_duplicate_idempotency_key(monkeypatch):
    company_id, connection_id = uuid4(), uuid4()
    existing = SimpleNamespace(company_id=company_id, idempotency_key="single-test-001")
    service = _single_message_service(monkeypatch, connection=_active_mailbox(company_id, connection_id), credential=_credential(company_id, connection_id), existing=existing)

    with pytest.raises(EmailSandboxRejectedError):
        service.preview_single_message(company_id=company_id, data=_single_message_payload(connection_id), actor=SimpleNamespace(id=uuid4()))

    assert service.audit.events[-1]["details"]["reason_code"] == "duplicate_idempotency_key"


def test_single_message_preview_enforces_working_hours(monkeypatch):
    company_id, connection_id = uuid4(), uuid4()
    service = _single_message_service(
        monkeypatch,
        connection=_active_mailbox(company_id, connection_id),
        credential=_credential(company_id, connection_id),
        policy={
            "enabled": True,
            "recipient_allowlist": ["allowed@example.test"],
            "sender_allowlist": ["sender@example.test"],
            "max_recipients_per_message": 1,
            "max_messages_per_hour": 5,
            "max_messages_per_day": 5,
            "required_subject_prefix": "[COMPANYAI TEST]",
            "working_hours": {"timezone": "UTC", "weekdays": [], "start": "09:00", "end": "17:00"},
        },
    )

    with pytest.raises(EmailSandboxRejectedError):
        service.preview_single_message(company_id=company_id, data=_single_message_payload(connection_id), actor=SimpleNamespace(id=uuid4()))

    assert service.audit.events[-1]["details"]["reason_code"] == "outside_working_hours"


def test_single_message_request_approval_records_dry_run_execution(monkeypatch):
    company_id, connection_id, actor_id = uuid4(), uuid4(), uuid4()
    service = _single_message_service(monkeypatch, connection=_active_mailbox(company_id, connection_id), credential=_credential(company_id, connection_id))
    payload = SingleMessageApprovalRequest(**_single_message_payload(connection_id).model_dump(), confirmation_text="CONFIRM ONE TEST EMAIL")

    result = service.request_single_message_approval(company_id=company_id, data=payload, actor=SimpleNamespace(id=actor_id))

    execution = service.executions.items[result.provider_execution_id]
    assert execution.execution_mode == "dry_run"
    assert execution.status == "pending_authorization"
    assert execution.provider_key == "generic_smtp_imap"
    assert execution.request_payload["payload_schema"] == "email_single_message_test.v1"
    assert "body" not in execution.request_payload
    assert service.approval_service.requests[-1].requested_conditions.payload_digest == result.payload_digest


def test_single_message_simulation_rejects_missing_approval(monkeypatch):
    company_id, connection_id, execution_id, actor_id = uuid4(), uuid4(), uuid4(), uuid4()
    service = _single_message_service(monkeypatch, connection=_active_mailbox(company_id, connection_id), credential=_credential(company_id, connection_id))
    execution = SimpleNamespace(id=execution_id, company_id=company_id, provider_connection_id=connection_id, provider_key="generic_smtp_imap", operation_key="send_email", requested_by_administrator_id=actor_id, request_payload={"payload_schema": "email_single_message_test.v1", "payload_digest": "a" * 64}, status="pending_authorization")
    service.executions.items[execution_id] = execution

    monkeypatch.setattr("app.services.email.AuthorizationEvaluatorService", lambda *args, **kwargs: FakeAuthorizer(status="approval_required"))
    with pytest.raises(EmailSandboxRejectedError):
        service.execute_single_message_simulation(company_id=company_id, data=SingleMessageSimulationRequest(provider_execution_id=execution_id, confirmation_text="CONFIRM SIMULATION ONLY"), actor=SimpleNamespace(id=actor_id))

    assert service.audit.events[-1]["details"]["reason_code"] == "approval_required"


def test_single_message_simulation_uses_dry_run_adapter_only(monkeypatch):
    company_id, connection_id, execution_id, actor_id = uuid4(), uuid4(), uuid4(), uuid4()
    service = _single_message_service(monkeypatch, connection=_active_mailbox(company_id, connection_id), credential=_credential(company_id, connection_id))
    execution = SimpleNamespace(id=execution_id, company_id=company_id, provider_connection_id=connection_id, provider_key="generic_smtp_imap", operation_key="send_email", requested_by_administrator_id=actor_id, request_payload={"payload_schema": "email_single_message_test.v1", "payload_digest": "b" * 64}, status="pending_authorization", authorization_reference=None, started_at=None, completed_at=None, result_metadata={}, idempotency_key="single-test-003")
    service.executions.items[execution_id] = execution

    monkeypatch.setattr("app.services.email.AuthorizationEvaluatorService", lambda *args, **kwargs: FakeAuthorizer(status="authorized"))
    result = service.execute_single_message_simulation(company_id=company_id, data=SingleMessageSimulationRequest(provider_execution_id=execution_id, confirmation_text="CONFIRM SIMULATION ONLY"), actor=SimpleNamespace(id=actor_id))

    assert result.external_action_taken is False
    assert result.provider_execution_id == execution_id
    assert execution.status == "succeeded"
    assert service.executions.attempts[-1].adapter_name == "dry-run"
