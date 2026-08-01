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
from app.schemas.email import EmailSandboxEmergencyStopUpdate, ReplyProposalWrite, SingleMessageApprovalRequest, SingleMessageLiveExecutionRequest, SingleMessageMode, SingleMessagePreviewRequest, SingleMessageSenderAllowlistUpdate, SingleMessageSimulationRequest, TestInboundEmailImport as InboundImportSchema
from app.services.email import EmailConflictError, EmailForbiddenError, EmailSandboxRejectedError, EmailWorkflowService, content_digest, reply_subject, single_message_digest
from app.services.generic_smtp_imap import GENERIC_MAILBOX_HEALTH_KEY, MailboxSendOutcomeUncertainError, MailboxSendResult
from app.services.audit_log import AuditLogService


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
    def __init__(self, *, fail=False):
        self.events = []
        self.fail = fail

    def append_company_event(self, **kwargs):
        if self.fail:
            raise ValueError("Unsupported company audit resource_type.")
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

    def transition(self, *, company_id, usage_id, status, actor_administrator_id, failure_code=None, commit=False):
        self.transitioned = True


class FakeEncryption:
    def decrypt(self, *_args, **_kwargs):
        return SimpleNamespace(secrets={"password": "synthetic-mailbox-password"})


class FakeLiveTransport:
    name = "fake-live-smtp"

    def __init__(self, *, outcome="accepted"):
        self.outcome = outcome
        self.calls = []

    def send_email(self, **kwargs):
        self.calls.append(kwargs)
        if self.outcome == "uncertain":
            raise MailboxSendOutcomeUncertainError
        return MailboxSendResult(status="accepted", accepted_at=datetime.now(UTC), server_response="accepted")


class FakeAllowlistSession:
    def __init__(self, *, existing=None):
        self.settings = {}
        self.committed = False
        self.rolled_back = False
        self.added = []
        if existing is not None:
            self.settings[existing.company_id] = existing

    def scalar(self, _statement):
        if len(self.settings) == 1:
            return next(iter(self.settings.values()))
        return None

    def add(self, item):
        self.added.append(item)
        self.settings[item.company_id] = item

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _allowlist_service(session=None, audit=None):
    session = session or FakeAllowlistSession()
    service = EmailWorkflowService.__new__(EmailWorkflowService)
    service.session = session
    service.audit = audit or FakeAudit()
    service.smtp_live_transport = FakeLiveTransport()
    service._sandbox_policy = lambda company_id: session.settings[company_id].value if company_id in session.settings else {
        "enabled": True,
        "recipient_allowlist": [],
        "sender_allowlist": [],
        "max_recipients_per_message": 1,
        "max_messages_per_hour": 5,
        "max_messages_per_day": 10,
        "required_subject_prefix": "[COMPANYAI TEST]",
        "emergency_stop": False,
    }
    return service


def _allowlist_update(value="Allowed@Example.TEST"):
    from app.schemas.email import SingleMessageRecipientAllowlistUpdate

    return SingleMessageRecipientAllowlistUpdate(recipient_email=value)


def _sender_update(value="Sender@Example.TEST"):
    return SingleMessageSenderAllowlistUpdate(sender_email=value)


def test_single_message_recipient_allowlist_adds_exact_recipient_safely():
    company_id, actor_id = uuid4(), uuid4()
    service = _allowlist_service()

    result = service.add_single_message_recipient_allowlist(company_id=company_id, data=_allowlist_update(), actor=SimpleNamespace(id=actor_id))

    assert result.recipient_allowlist == ["allowed@example.test"]
    assert service.session.committed is True
    event = service.audit.events[-1]
    assert event["resource_type"] == "email_automation"
    assert event["action"] == "email_automation.settings_updated"
    assert event["details"] == {
        "operation": "single_message_recipient_allowlist_updated",
        "changed": True,
        "recipient_count": 1,
    }
    assert "allowed@example.test" not in repr(event)


def test_single_message_recipient_allowlist_listing_uses_configured_recipients():
    company_id = uuid4()
    session = FakeAllowlistSession(existing=SimpleNamespace(company_id=company_id, value={"recipient_allowlist": ["B@Example.TEST", "a@example.test", "@example.test", "*.example.test"]}))
    service = _allowlist_service(session=session)

    result = service.single_message_recipient_allowlist(company_id=company_id)

    assert result.recipient_allowlist == ["a@example.test", "b@example.test"]


def test_single_message_recipient_allowlist_duplicate_is_normalized_noop():
    company_id, actor_id = uuid4(), uuid4()
    session = FakeAllowlistSession(existing=SimpleNamespace(company_id=company_id, value={"recipient_allowlist": ["allowed@example.test"]}))
    service = _allowlist_service(session=session)

    result = service.add_single_message_recipient_allowlist(company_id=company_id, data=_allowlist_update("ALLOWED@example.test"), actor=SimpleNamespace(id=actor_id))

    assert result.recipient_allowlist == ["allowed@example.test"]
    assert service.audit.events[-1]["details"]["changed"] is False
    assert service.audit.events[-1]["details"]["recipient_count"] == 1


def test_single_message_recipient_allowlist_removes_recipient_safely():
    company_id, actor_id = uuid4(), uuid4()
    session = FakeAllowlistSession(existing=SimpleNamespace(company_id=company_id, value={"recipient_allowlist": ["allowed@example.test", "other@example.test"]}))
    service = _allowlist_service(session=session)

    result = service.remove_single_message_recipient_allowlist(company_id=company_id, data=_allowlist_update("allowed@example.test"), actor=SimpleNamespace(id=actor_id))

    assert result.recipient_allowlist == ["other@example.test"]
    assert service.audit.events[-1]["resource_type"] == "email_automation"
    assert service.audit.events[-1]["details"] == {
        "operation": "single_message_recipient_allowlist_removed",
        "changed": True,
        "recipient_count": 1,
    }
    assert "allowed@example.test" not in repr(service.audit.events[-1])


def test_single_message_recipient_allowlist_is_company_isolated():
    company_a, company_b = uuid4(), uuid4()
    service = _allowlist_service()

    service.add_single_message_recipient_allowlist(company_id=company_a, data=_allowlist_update("allowed@example.test"), actor=SimpleNamespace(id=uuid4()))

    assert service.single_message_recipient_allowlist(company_id=company_a).recipient_allowlist == ["allowed@example.test"]
    assert service.single_message_recipient_allowlist(company_id=company_b).recipient_allowlist == []


def test_single_message_recipient_allowlist_rolls_back_when_audit_fails():
    company_id = uuid4()
    session = FakeAllowlistSession()
    service = _allowlist_service(session=session, audit=FakeAudit(fail=True))

    with pytest.raises(ValueError):
        service.add_single_message_recipient_allowlist(company_id=company_id, data=_allowlist_update(), actor=SimpleNamespace(id=uuid4()))

    assert session.committed is False
    assert session.rolled_back is True
    assert service.smtp_live_transport.calls == []


def test_email_sandbox_status_lists_sender_recipient_and_emergency_state():
    company_id = uuid4()
    session = FakeAllowlistSession(existing=SimpleNamespace(company_id=company_id, value={
        "recipient_allowlist": ["Allowed@Example.TEST"],
        "sender_allowlist": ["Sender@Example.TEST", "@example.test"],
        "emergency_stop": True,
        "max_recipients_per_message": 1,
        "max_messages_per_hour": 5,
        "max_messages_per_day": 10,
        "required_subject_prefix": "[COMPANYAI TEST]",
        "approval_required": True,
    }))
    service = _allowlist_service(session=session)

    result = service.email_sandbox_status(company_id=company_id)

    assert result.recipient_allowlist == ["allowed@example.test"]
    assert result.sender_allowlist == ["sender@example.test"]
    assert result.emergency_stop is True
    assert result.emergency_stop_status == "active"


def test_email_sandbox_management_permission_is_admin_scoped():
    assert role_has_permission(CompanyRole.OWNER.value, CompanyPermission.PROVIDER_EXECUTIONS_MANAGE)
    assert role_has_permission(CompanyRole.ADMIN.value, CompanyPermission.PROVIDER_EXECUTIONS_MANAGE)
    assert not role_has_permission(CompanyRole.OPERATOR.value, CompanyPermission.PROVIDER_EXECUTIONS_MANAGE)
    assert not role_has_permission(CompanyRole.VIEWER.value, CompanyPermission.PROVIDER_EXECUTIONS_MANAGE)


def test_single_message_sender_allowlist_adds_exact_sender_safely():
    company_id, actor_id = uuid4(), uuid4()
    service = _allowlist_service()

    result = service.add_single_message_sender_allowlist(company_id=company_id, data=_sender_update(), actor=SimpleNamespace(id=actor_id))

    assert result.sender_allowlist == ["sender@example.test"]
    event = service.audit.events[-1]
    assert event["resource_type"] == "email_automation"
    assert event["action"] == "email_automation.settings_updated"
    assert event["details"] == {
        "operation": "single_message_sender_allowlist_updated",
        "changed": True,
        "sender_count": 1,
    }
    assert "sender@example.test" not in repr(event)


def test_single_message_sender_allowlist_duplicate_is_normalized_noop():
    company_id = uuid4()
    session = FakeAllowlistSession(existing=SimpleNamespace(company_id=company_id, value={"sender_allowlist": ["sender@example.test"]}))
    service = _allowlist_service(session=session)

    result = service.add_single_message_sender_allowlist(company_id=company_id, data=_sender_update("SENDER@example.test"), actor=SimpleNamespace(id=uuid4()))

    assert result.sender_allowlist == ["sender@example.test"]
    assert service.audit.events[-1]["details"]["changed"] is False
    assert service.audit.events[-1]["details"]["sender_count"] == 1


def test_single_message_sender_allowlist_rejects_wildcard_and_domain():
    with pytest.raises(ValidationError):
        SingleMessageSenderAllowlistUpdate(sender_email="*@example.test")
    with pytest.raises(ValidationError):
        SingleMessageSenderAllowlistUpdate(sender_email="@example.test")


def test_single_message_sender_allowlist_removes_sender_safely():
    company_id = uuid4()
    session = FakeAllowlistSession(existing=SimpleNamespace(company_id=company_id, value={"sender_allowlist": ["sender@example.test", "other@example.test"]}))
    service = _allowlist_service(session=session)

    result = service.remove_single_message_sender_allowlist(company_id=company_id, data=_sender_update("sender@example.test"), actor=SimpleNamespace(id=uuid4()))

    assert result.sender_allowlist == ["other@example.test"]
    assert service.audit.events[-1]["details"] == {
        "operation": "single_message_sender_allowlist_removed",
        "changed": True,
        "sender_count": 1,
    }
    assert "sender@example.test" not in repr(service.audit.events[-1])


def test_single_message_sender_allowlist_can_select_tested_mailbox_without_credentials():
    company_id = uuid4()
    connection_id = uuid4()
    service = _allowlist_service()
    service._mailbox_sender = lambda **_kwargs: (SimpleNamespace(id=connection_id), "mailbox-sender@example.test")

    result = service.add_single_message_sender_allowlist(company_id=company_id, data=SingleMessageSenderAllowlistUpdate(provider_connection_id=connection_id), actor=SimpleNamespace(id=uuid4()))

    assert result.sender_allowlist == ["mailbox-sender@example.test"]
    assert service.smtp_live_transport.calls == []


def test_single_message_sender_allowlist_rejects_untested_mailbox_selection():
    company_id = uuid4()
    service = _allowlist_service()

    def reject_mailbox(**kwargs):
        service._reject_single_message(kwargs["company_id"], kwargs["actor"], "smtp_not_tested")

    service._mailbox_sender = reject_mailbox

    with pytest.raises(EmailSandboxRejectedError) as exc:
        service.add_single_message_sender_allowlist(company_id=company_id, data=SingleMessageSenderAllowlistUpdate(provider_connection_id=uuid4()), actor=SimpleNamespace(id=uuid4()))

    assert exc.value.reason_code == "smtp_not_tested"
    assert service.smtp_live_transport.calls == []


def test_email_sandbox_emergency_stop_requires_explicit_disable_confirmation():
    with pytest.raises(ValidationError):
        EmailSandboxEmergencyStopUpdate(emergency_stop=False, confirmation_text="disable")


def test_email_sandbox_emergency_stop_disable_and_enable_are_audited_safely():
    company_id = uuid4()
    session = FakeAllowlistSession(existing=SimpleNamespace(company_id=company_id, value={"emergency_stop": True}))
    service = _allowlist_service(session=session)

    disabled = service.update_email_sandbox_emergency_stop(
        company_id=company_id,
        data=EmailSandboxEmergencyStopUpdate(emergency_stop=False, confirmation_text="DISABLE EMAIL EMERGENCY STOP"),
        actor=SimpleNamespace(id=uuid4()),
    )
    enabled = service.update_email_sandbox_emergency_stop(
        company_id=company_id,
        data=EmailSandboxEmergencyStopUpdate(emergency_stop=True),
        actor=SimpleNamespace(id=uuid4()),
    )

    assert disabled.emergency_stop is False
    assert enabled.emergency_stop is True
    assert service.audit.events[-2]["details"] == {
        "operation": "email_sandbox_emergency_stop_updated",
        "changed": True,
        "status": "inactive",
    }
    assert service.audit.events[-1]["details"] == {
        "operation": "email_sandbox_emergency_stop_updated",
        "changed": True,
        "status": "active",
    }
    assert "DISABLE EMAIL EMERGENCY STOP" not in repr(service.audit.events)


def test_one_test_email_audit_shapes_use_supported_contracts():
    class CapturingAuditRepository:
        def __init__(self):
            self.events = []

        def create(self, **values):
            self.events.append(values)
            return SimpleNamespace(**values)

    repository = CapturingAuditRepository()
    audit = AuditLogService(repository)  # type: ignore[arg-type]
    company_id, actor_id, resource_id = uuid4(), uuid4(), uuid4()
    events = [
        ("email_automation.settings_updated", "email_automation", None, {"operation": "single_message_recipient_allowlist_updated", "changed": True, "recipient_count": 1}),
        ("email_automation.settings_updated", "email_automation", None, {"operation": "single_message_sender_allowlist_updated", "changed": True, "sender_count": 1}),
        ("email_automation.settings_updated", "email_automation", None, {"operation": "email_sandbox_emergency_stop_updated", "changed": True, "status": "inactive"}),
        ("email_single_message.simulated", "email_single_message_test", None, {"message_digest": "a" * 64, "simulation_only": True, "live_send_available": False}),
        ("email_single_message.approval_requested", "email_single_message_test", resource_id, {"provider_execution_id": str(resource_id), "approval_request_id": str(uuid4()), "message_digest": "b" * 64, "simulation_only": False, "live_send_available": True}),
        ("provider_execution.requested", "provider_execution", resource_id, {"provider_key": "generic_smtp_imap", "operation_key": "send_email", "execution_mode": "live", "simulation_only": False, "live_send_available": True}),
        ("provider_execution.authorized", "provider_execution", resource_id, {"policy_id": str(uuid4()), "usage_id": str(uuid4()), "operation_key": "send_email", "live_send_available": True}),
        ("provider_execution.started", "provider_execution", resource_id, {"operation_key": "send_email", "attempt_number": 1, "live_send_available": True}),
        ("provider_execution.failed", "provider_execution", resource_id, {"operation_key": "send_email", "status": "failed_before_send", "category": "connection_failed", "message_digest": "c" * 64, "live_send_available": True}),
    ]

    for action, resource_type, item_id, details in events:
        audit.append_company_event(company_id=company_id, actor_administrator_id=actor_id, action=action, resource_type=resource_type, resource_id=item_id, details=details)

    serialized = repr(repository.events)
    assert "allowed@example.test" not in serialized
    assert "Exact single-message body" not in serialized
    assert "password" not in serialized


def _single_message_service(monkeypatch, *, connection=None, credential=None, existing=None, policy=None, sent_count=0, live_transport=None):
    from app.core.config import get_settings

    monkeypatch.setenv("APP_ENV", "local-production")
    get_settings.cache_clear()
    service = EmailWorkflowService.__new__(EmailWorkflowService)
    service.session = SimpleNamespace(commit=lambda: None, rollback=lambda: None, flush=lambda: None)
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
    service.encryption = FakeEncryption()
    service.smtp_live_transport = live_transport or FakeLiveTransport()
    return service


def _active_mailbox(company_id, connection_id):
    return SimpleNamespace(
        id=connection_id,
        company_id=company_id,
        provider_key="generic_smtp_imap",
        status="active",
        configuration={"email_address": "sender@example.test", "username": "sender@example.test", "smtp_host": "mail.example.test", "smtp_port": 465, "smtp_security": "ssl_tls"},
        metadata_={GENERIC_MAILBOX_HEALTH_KEY: {"smtp": {"status": "succeeded"}, "imap": {"status": "succeeded"}}},
    )


def _credential(company_id, connection_id):
    return SimpleNamespace(id=uuid4(), company_id=company_id, provider_connection_id=connection_id, expires_at=datetime.now(UTC) + timedelta(days=1), encrypted_payload=b"ciphertext", nonce=b"123456789012", encryption_version=2, encryption_key_id="legacy")


def _single_message_payload(connection_id):
    return SingleMessagePreviewRequest(
        provider_connection_id=connection_id,
        recipient_email="allowed@example.test",
        subject="[COMPANYAI TEST] Controlled hello",
        body="One controlled message body.",
        idempotency_key="single-test-001",
    )


def _single_message_approval_payload(connection_id, *, mode="simulation"):
    values = _single_message_payload(connection_id).model_dump()
    values["mode"] = mode
    preview_digest = single_message_digest(
        provider_connection_id=connection_id,
        sender_email="sender@example.test",
        recipient_email=values["recipient_email"],
        subject=values["subject"],
        body=values["body"],
    )
    return SingleMessageApprovalRequest(**values, preview_payload_digest=preview_digest, confirmation_text="CONFIRM ONE TEST EMAIL")


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


def test_single_message_preview_rejects_non_allowlisted_sender_with_policy_checks(monkeypatch):
    company_id, connection_id = uuid4(), uuid4()
    service = _single_message_service(
        monkeypatch,
        connection=_active_mailbox(company_id, connection_id),
        credential=_credential(company_id, connection_id),
        policy={
            "enabled": True,
            "recipient_allowlist": ["allowed@example.test"],
            "sender_allowlist": [],
            "max_recipients_per_message": 1,
            "max_messages_per_hour": 5,
            "max_messages_per_day": 10,
            "required_subject_prefix": "[COMPANYAI TEST]",
            "emergency_stop": False,
        },
    )

    with pytest.raises(EmailSandboxRejectedError) as exc:
        service.preview_single_message(company_id=company_id, data=_single_message_payload(connection_id), actor=SimpleNamespace(id=uuid4()))

    assert exc.value.reason_code == "sender_not_allowlisted"
    assert exc.value.policy_checks["recipient_allowlisted"] is True
    assert exc.value.policy_checks["sender_allowlisted"] is False


def test_single_message_preview_succeeds_after_sender_is_allowlisted(monkeypatch):
    company_id, connection_id = uuid4(), uuid4()
    service = _single_message_service(monkeypatch, connection=_active_mailbox(company_id, connection_id), credential=_credential(company_id, connection_id))

    result = service.preview_single_message(company_id=company_id, data=_single_message_payload(connection_id), actor=SimpleNamespace(id=uuid4()))

    assert result.sender_email == "sender@example.test"
    assert result.policy_checks["sender_allowlisted"] is True
    assert result.policy_checks["recipient_allowlisted"] is True


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
    payload = _single_message_approval_payload(connection_id)

    result = service.request_single_message_approval(company_id=company_id, data=payload, actor=SimpleNamespace(id=actor_id))

    execution = service.executions.items[result.provider_execution_id]
    assert execution.execution_mode == "dry_run"
    assert execution.status == "pending_authorization"
    assert execution.provider_key == "generic_smtp_imap"
    assert execution.request_payload["payload_schema"] == "email_single_message_test.v1"
    assert execution.request_payload["body"] == "One controlled message body."
    assert service.approval_service.requests[-1].requested_conditions.payload_digest == result.payload_digest


def test_single_message_live_approval_records_live_execution_without_body(monkeypatch):
    company_id, connection_id, actor_id = uuid4(), uuid4(), uuid4()
    service = _single_message_service(monkeypatch, connection=_active_mailbox(company_id, connection_id), credential=_credential(company_id, connection_id))
    payload = _single_message_approval_payload(connection_id, mode="live_test")

    result = service.request_single_message_approval(company_id=company_id, data=payload, actor=SimpleNamespace(id=actor_id))

    execution = service.executions.items[result.provider_execution_id]
    assert execution.execution_mode == "live"
    assert execution.request_payload["mode"] == "live_test"
    assert execution.request_payload["body"] == "One controlled message body."
    assert result.live_send_available is True
    assert result.simulation_only is False


def test_single_message_request_approval_rejects_stale_preview_digest(monkeypatch):
    company_id, connection_id = uuid4(), uuid4()
    service = _single_message_service(monkeypatch, connection=_active_mailbox(company_id, connection_id), credential=_credential(company_id, connection_id))
    values = _single_message_payload(connection_id).model_dump()
    payload = SingleMessageApprovalRequest(**values, preview_payload_digest="0" * 64, confirmation_text="CONFIRM ONE TEST EMAIL")

    with pytest.raises(EmailConflictError):
        service.request_single_message_approval(company_id=company_id, data=payload, actor=SimpleNamespace(id=uuid4()))


def test_single_message_simulation_preview_available_while_emergency_stop_is_active(monkeypatch):
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
            "max_messages_per_day": 10,
            "required_subject_prefix": "[COMPANYAI TEST]",
            "emergency_stop": True,
        },
    )

    result = service.preview_single_message(company_id=company_id, data=_single_message_payload(connection_id), actor=SimpleNamespace(id=uuid4()))

    assert result.simulation_only is True
    assert result.live_send_available is False
    assert result.policy_checks["emergency_stop_disabled"] is False


def test_single_message_live_preview_blocked_while_emergency_stop_is_active(monkeypatch):
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
            "max_messages_per_day": 10,
            "required_subject_prefix": "[COMPANYAI TEST]",
            "emergency_stop": True,
        },
    )

    with pytest.raises(EmailSandboxRejectedError) as exc:
        service.preview_single_message(company_id=company_id, data=_single_message_payload(connection_id).model_copy(update={"mode": SingleMessageMode.LIVE_TEST}), actor=SimpleNamespace(id=uuid4()))

    assert exc.value.reason_code == "emergency_stop_enabled"
    assert service.smtp_live_transport.calls == []


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


def _live_execution(company_id, connection_id, execution_id, actor_id, *, body="One controlled message body."):
    digest = single_message_digest(provider_connection_id=connection_id, sender_email="sender@example.test", recipient_email="allowed@example.test", subject="[COMPANYAI TEST] Controlled hello", body=body)
    return SimpleNamespace(id=execution_id, company_id=company_id, provider_connection_id=connection_id, provider_key="generic_smtp_imap", operation_key="send_email", execution_mode="live", requested_by_administrator_id=actor_id, request_payload={"payload_schema": "email_single_message_test.v1", "mode": "live_test", "sender_email": "sender@example.test", "recipient_email": "allowed@example.test", "subject": "[COMPANYAI TEST] Controlled hello", "payload_digest": digest}, status="pending_authorization", authorization_reference=None, started_at=None, completed_at=None, result_metadata={}, error_category=None, error_message=None, idempotency_key="single-live-001")


def test_single_message_live_executes_fake_smtp_after_approval(monkeypatch):
    company_id, connection_id, execution_id, actor_id = uuid4(), uuid4(), uuid4(), uuid4()
    transport = FakeLiveTransport()
    service = _single_message_service(monkeypatch, connection=_active_mailbox(company_id, connection_id), credential=_credential(company_id, connection_id), live_transport=transport)
    execution = _live_execution(company_id, connection_id, execution_id, actor_id)
    service.executions.items[execution_id] = execution
    monkeypatch.setattr("app.services.email.AuthorizationEvaluatorService", lambda *args, **kwargs: FakeAuthorizer(status="authorized"))

    result = service.execute_single_message_live(company_id=company_id, data=SingleMessageLiveExecutionRequest(provider_execution_id=execution_id, subject="[COMPANYAI TEST] Controlled hello", body="One controlled message body.", confirmation_text="SEND ONE TEST EMAIL"), actor=SimpleNamespace(id=actor_id))

    assert result.status == "succeeded"
    assert result.external_action_taken is True
    assert execution.status == "succeeded"
    assert service.executions.attempts[-1].adapter_name == "fake-live-smtp"
    assert transport.calls[0]["password"] == "synthetic-mailbox-password"
    assert "synthetic-mailbox-password" not in repr(execution.result_metadata)
    assert "One controlled message body." not in repr(execution.result_metadata)


def test_single_message_live_outcome_uncertain_does_not_retry(monkeypatch):
    company_id, connection_id, execution_id, actor_id = uuid4(), uuid4(), uuid4(), uuid4()
    transport = FakeLiveTransport(outcome="uncertain")
    service = _single_message_service(monkeypatch, connection=_active_mailbox(company_id, connection_id), credential=_credential(company_id, connection_id), live_transport=transport)
    execution = _live_execution(company_id, connection_id, execution_id, actor_id)
    service.executions.items[execution_id] = execution
    monkeypatch.setattr("app.services.email.AuthorizationEvaluatorService", lambda *args, **kwargs: FakeAuthorizer(status="authorized"))

    result = service.execute_single_message_live(company_id=company_id, data=SingleMessageLiveExecutionRequest(provider_execution_id=execution_id, subject="[COMPANYAI TEST] Controlled hello", body="One controlled message body.", confirmation_text="SEND ONE TEST EMAIL"), actor=SimpleNamespace(id=actor_id))

    assert result.status == "outcome_uncertain"
    assert result.external_action_taken is True
    assert len(transport.calls) == 1
    assert service.executions.attempts[-1].status == "outcome_uncertain"
    with pytest.raises(EmailConflictError):
        service.execute_single_message_live(company_id=company_id, data=SingleMessageLiveExecutionRequest(provider_execution_id=execution_id, subject="[COMPANYAI TEST] Controlled hello", body="One controlled message body.", confirmation_text="SEND ONE TEST EMAIL"), actor=SimpleNamespace(id=actor_id))
    assert len(transport.calls) == 1


def test_single_message_live_rejects_changed_body_before_smtp(monkeypatch):
    company_id, connection_id, execution_id, actor_id = uuid4(), uuid4(), uuid4(), uuid4()
    transport = FakeLiveTransport()
    service = _single_message_service(monkeypatch, connection=_active_mailbox(company_id, connection_id), credential=_credential(company_id, connection_id), live_transport=transport)
    execution = _live_execution(company_id, connection_id, execution_id, actor_id)
    service.executions.items[execution_id] = execution
    monkeypatch.setattr("app.services.email.AuthorizationEvaluatorService", lambda *args, **kwargs: FakeAuthorizer(status="authorized"))

    with pytest.raises(EmailForbiddenError):
        service.execute_single_message_live(company_id=company_id, data=SingleMessageLiveExecutionRequest(provider_execution_id=execution_id, subject="[COMPANYAI TEST] Controlled hello", body="Changed body.", confirmation_text="SEND ONE TEST EMAIL"), actor=SimpleNamespace(id=actor_id))

    assert transport.calls == []
