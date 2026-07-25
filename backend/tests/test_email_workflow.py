"""Focused contract and safety tests for the thin email workflow."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.core.company_permissions import CompanyPermission, role_has_permission
from app.core.provider_execution import LocalTestEmailAdapter, provider_operation_registry
from app.models.company_membership import CompanyRole
from app.schemas.approval import AuthorizationConditionsV1
from app.schemas.email import ReplyProposalWrite, TestInboundEmailImport as InboundImportSchema
from app.services.email import content_digest, reply_subject


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
