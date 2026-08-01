"""Focused contract tests for the Provider Execution foundation."""
from pathlib import Path
import ast
from types import SimpleNamespace
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.core.provider_execution import (
    DryRunProviderAdapter, ExecutionMode, ExecutionRisk,
    ProviderOperationRegistry, UnsupportedProviderAdapter, provider_operation_registry,
)
from app.models.provider_execution import ProviderExecution, ProviderExecutionAttempt
from app.models.audit_log import AuditAction
from app.schemas.provider_execution import ProviderExecutionAuthorize, ProviderExecutionCreate, ProviderOperationResponse
from app.main import app
from app.services.provider_execution import ExecutionConflictError, ExecutionDeniedError, ProviderExecutionService, _redact


class _Session:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _ExecutionRepository:
    def __init__(self, item):
        self.item = item
        self.attempts = []

    def get(self, company_id, execution_id, lock=False):
        return self.item if (self.item.company_id, self.item.id) == (company_id, execution_id) else None

    def add_attempt(self, attempt):
        self.attempts.append(attempt)


class _Audit:
    def __init__(self):
        self.events = []

    def append_company_event(self, **event):
        self.events.append(event)


class _Authorizer:
    def __init__(self, decision):
        self.decision = decision
        self.reservations = []
        self.transitions = []

    def evaluate(self, action):
        self.action = action
        return self.decision

    def reserve(self, reservation, *, commit=True):
        self.reservations.append((reservation, commit))
        return SimpleNamespace(id=uuid4())

    def transition(self, **values):
        self.transitions.append(values)


def _execution_service(decision):
    company_id, execution_id, administrator_id = uuid4(), uuid4(), uuid4()
    item = SimpleNamespace(
        id=execution_id,
        company_id=company_id,
        provider_connection_id=uuid4(),
        provider_key="twilio",
        operation_key="create_call",
        execution_mode="dry_run",
        status="pending_authorization",
        requested_by_administrator_id=administrator_id,
        requested_by_agent_id=None,
        authorization_reference=None,
        idempotency_key="approval-bound-execution",
        request_payload={"safe": "value"},
        result_metadata={},
        started_at=None,
        completed_at=None,
        error_category=None,
        error_message=None,
    )
    service = ProviderExecutionService.__new__(ProviderExecutionService)
    service.session = _Session()
    service.repo = _ExecutionRepository(item)
    service.audit = _Audit()
    service.authorizer = _Authorizer(decision)
    return service, item, SimpleNamespace(id=administrator_id)


def test_registry_has_local_test_email_operation():
    items = provider_operation_registry.all()
    assert len(items) == 24
    assert {item.provider_key for item in items} == {"retell", "twilio", "telnyx", "microsoft_365", "google_workspace", "lemlist", "instantly", "smartlead", "local_test_email", "generic_smtp_imap"}
    local = provider_operation_registry.require("local_test_email", "send_email")
    assert local.implemented is True and local.required_credential_status == "not_required"
    generic = provider_operation_registry.require("generic_smtp_imap", "send_email")
    assert generic.implemented is False and generic.retry_attempts == 0 and generic.approval_required is True


def test_registry_exact_lookup_unknown_and_duplicate_rejection():
    item = provider_operation_registry.require("retell", "list_agents")
    assert provider_operation_registry.get("retell", "list_agents") is item
    assert provider_operation_registry.get("retell", "missing") is None
    with pytest.raises(ValueError): provider_operation_registry.require("missing", "list_agents")
    registry = ProviderOperationRegistry(); registry.register(item)
    with pytest.raises(ValueError): registry.register(item)


def test_descriptors_are_immutable_and_safe():
    item = provider_operation_registry.require("twilio", "create_call")
    with pytest.raises(AttributeError): item.operation_key = "changed"  # type: ignore[misc]
    assert item.approval_required is True and item.implemented is False
    assert item.supported_execution_modes == frozenset({ExecutionMode.DRY_RUN, ExecutionMode.LIVE})
    assert all(x.risk_level in set(ExecutionRisk) for x in provider_operation_registry.all())


def test_dry_run_is_deterministic_and_live_fails_closed():
    item = provider_operation_registry.require("retell", "list_agents")
    adapter = DryRunProviderAdapter()
    assert adapter.execute(item, {"safe": "value"}, idempotency_key="idem") == adapter.execute(item, {"safe": "value"}, idempotency_key="idem")
    with pytest.raises(RuntimeError, match="not implemented"):
        UnsupportedProviderAdapter().execute(item, {}, idempotency_key="idem")


def test_recursive_redaction_preserves_safe_metadata():
    value = _redact({"name": "safe", "nested": {"api_key": "secret", "authorization": "Bearer token", "items": [{"password": "pw"}]}})
    assert value["name"] == "safe"
    assert value["nested"]["api_key"] == "[REDACTED]"
    assert value["nested"]["items"][0]["password"] == "[REDACTED]"
    assert "secret" not in repr(value) and "Bearer token" not in repr(value)


def test_execution_schema_forbids_unknown_fields_and_response_has_no_credentials():
    with pytest.raises(ValidationError): ProviderExecutionCreate(provider_connection_id="00000000-0000-0000-0000-000000000001", provider_key="retell", operation_key="list_agents", idempotency_key="x", unexpected=True)
    schema = str(app.openapi())
    assert "encrypted_payload" not in schema and "nonce" not in schema
    with pytest.raises(ValidationError):
        ProviderExecutionAuthorize(authorization_policy_id=None, unsafe_metadata={})


def test_model_constraints_cover_lineage_lifecycle_and_attempt_number():
    execution_constraints = {c.name for c in ProviderExecution.__table__.constraints if c.name}
    attempt_constraints = {c.name for c in ProviderExecutionAttempt.__table__.constraints if c.name}
    assert {"fk_provider_executions_company_connection", "fk_provider_executions_authorization_policy", "uq_provider_executions_company_id", "uq_provider_executions_company_idempotency", "ck_provider_executions_one_requester", "ck_provider_executions_status"} <= execution_constraints
    assert {"fk_provider_execution_attempts_execution", "uq_provider_execution_attempts_number", "ck_provider_execution_attempts_number"} <= attempt_constraints
    assert all(fk.ondelete == "RESTRICT" for model in (ProviderExecution, ProviderExecutionAttempt) for fk in model.__table__.foreign_keys)


def test_audit_actions_and_routes_are_registered():
    expected = {"provider_execution." + x for x in ("requested", "authorized", "denied", "started", "succeeded", "failed", "cancelled")}
    assert {item.value for item in AuditAction if item.value.startswith("provider_execution.")} == expected
    paths = app.openapi()["paths"]
    assert "/api/v1/provider-operations" in paths
    assert "/api/v1/companies/{company_id}/provider-executions" in paths
    assert "/api/v1/internal/agents/provider-executions" in paths
    security_schemes = app.openapi()["components"]["securitySchemes"]
    assert "HTTPBearer" in security_schemes
    assert security_schemes["HTTPBearer"]["type"] == "http"
    assert security_schemes["HTTPBearer"]["scheme"] == "bearer"
    for path, method in (
        ("/api/v1/provider-operations", "get"),
        ("/api/v1/provider-operations/{provider_key}/{operation_key}", "get"),
        ("/api/v1/companies/{company_id}/provider-executions", "post"),
        ("/api/v1/companies/{company_id}/provider-executions", "get"),
    ):
        assert paths[path][method]["security"] == [{"HTTPBearer": []}]
    for path, method in (
        ("/api/v1/internal/agents/provider-operations", "get"),
        ("/api/v1/internal/agents/provider-executions", "post"),
        ("/api/v1/internal/agents/provider-executions/{execution_id}/execute-dry-run", "post"),
    ):
        assert paths[path][method]["security"] == [{"HTTPBearer": []}]


def test_migration_revision_chain_and_static_safety():
    source = Path(__file__).parents[1] / "migrations/versions/0011_provider_execution.py"
    text = source.read_text(encoding="utf-8")
    assert 'revision = "0011_provider_execution"' in text
    assert 'down_revision = "0010_provider_connections"' in text
    assert '"provider_executions"' in text and '"provider_execution_attempts"' in text
    assert "fk_authorization_usages_provider_execution" in text
    assert "fk_provider_executions_authorization_policy" in text
    assert "ck_provider_executions_one_requester" in text
    assert "op.drop_table(\"provider_execution_attempts\")" in text
    tree = ast.parse(text)
    assert not any(isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("app") for n in ast.walk(tree))


def test_approval_required_execution_fails_closed_before_attempt():
    service, item, administrator = _execution_service(
        SimpleNamespace(status="approval_required", policy_id=None, reason_code="approval_required")
    )
    with pytest.raises(ExecutionDeniedError, match="authorization_required"):
        service.execute_dry_run(
            company_id=item.company_id,
            execution_id=item.id,
            administrator=administrator,
        )
    assert item.status == "pending_authorization"
    assert service.repo.attempts == []
    assert service.authorizer.reservations == []
    assert [event["action"] for event in service.audit.events] == ["provider_execution.denied"]


def test_approved_policy_is_reserved_before_attempt_and_consumed_atomically():
    policy_id = uuid4()
    service, item, administrator = _execution_service(
        SimpleNamespace(status="authorized", policy_id=policy_id, reason_code="policy_allow")
    )
    result = service.execute_dry_run(
        company_id=item.company_id,
        execution_id=item.id,
        administrator=administrator,
        authorization_policy_id=policy_id,
    )
    assert result.status == "succeeded"
    assert result.authorization_reference == policy_id
    assert len(service.repo.attempts) == 1
    reservation, commit = service.authorizer.reservations[0]
    assert reservation.execution_id == item.id
    assert reservation.reservation_key == item.id
    assert commit is False
    assert service.authorizer.transitions[0]["status"] == "succeeded"
    assert service.authorizer.transitions[0]["commit"] is False
    assert [event["action"] for event in service.audit.events] == [
        "provider_execution.authorized",
        "provider_execution.started",
        "provider_execution.succeeded",
    ]


def test_wrong_explicit_policy_fails_closed_without_attempt():
    selected_policy_id = uuid4()
    service, item, administrator = _execution_service(
        SimpleNamespace(status="authorized", policy_id=uuid4(), reason_code="policy_allow")
    )
    with pytest.raises(ExecutionDeniedError):
        service.execute_dry_run(
            company_id=item.company_id,
            execution_id=item.id,
            administrator=administrator,
            authorization_policy_id=selected_policy_id,
        )
    assert service.repo.attempts == []
    assert service.authorizer.reservations == []


def test_terminal_or_cancelled_execution_cannot_be_reauthorized():
    policy_id = uuid4()
    for terminal_status in ("succeeded", "failed", "cancelled", "denied"):
        service, item, administrator = _execution_service(
            SimpleNamespace(status="authorized", policy_id=policy_id, reason_code="policy_allow")
        )
        item.status = terminal_status
        with pytest.raises(ExecutionConflictError):
            service.execute_dry_run(
                company_id=item.company_id,
                execution_id=item.id,
                administrator=administrator,
                authorization_policy_id=policy_id,
            )
        assert service.repo.attempts == []
