"""Focused security and authorization tests for Tool Registry."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.dependencies.agent_authentication import require_current_agent
from app.core.company_permissions import CompanyPermission, role_has_permission
from app.core.tool_registry import RuntimeToolDescriptor, RuntimeToolRegistry, validate_tool_key
from app.main import app
from app.models.audit_log import AuditAction
from app.models.tool_registry import AgentToolGrant, CompanyTool, ToolDefinition
from app.schemas.tool_registry import ToolDefinitionCreate, ToolDefinitionUpdate
from app.services.agent_identity import AuthenticatedAgent
from app.services.tool_registry import ToolAuthorizationError, ToolRegistryService, get_tool_registry_service, tool_authorization_action

NOW = datetime.now(UTC)


def tool(**overrides):
    values = dict(id=uuid4(), key="email.send", display_name="Send email", description="Send an approved email.", category="email", risk_level="high", execution_mode="provider", requires_approval=True, status="active", input_schema={}, output_schema={}, metadata_={}, is_system=False, created_at=NOW, updated_at=NOW)
    values.update(overrides)
    return SimpleNamespace(**values)


def agent(**overrides):
    values = dict(id=uuid4(), company_id=uuid4(), name="Agent", slug="agent", agent_type="general", status="active", is_system=False)
    values.update(overrides)
    return SimpleNamespace(**values)


def credential(item, **overrides):
    values = dict(id=uuid4(), company_id=item.company_id, agent_id=item.id, status="active", expires_at=None)
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize("value", ["email.send", "phone.call", "lead.research", "campaign.manage", "email.send_v2"])
def test_valid_tool_keys_are_exact(value: str) -> None:
    assert validate_tool_key(value) == value


@pytest.mark.parametrize("value", ["Email.send", "email.*", " email.send", "email.send ", ".email", "email.", "email..send", "email.2send", "emailsend"])
def test_invalid_tool_keys_are_rejected_without_normalization(value: str) -> None:
    with pytest.raises(ValueError):
        validate_tool_key(value)


def test_tool_schema_rejects_duplicate_meaning_and_high_risk_without_approval() -> None:
    with pytest.raises(ValidationError):
        ToolDefinitionCreate(key="EMAIL.SEND", display_name="Send", description="x", category="email", risk_level="low", execution_mode="provider")
    with pytest.raises(ValidationError):
        ToolDefinitionCreate(key="email.send", display_name="Send", description="x", category="email", risk_level="critical", execution_mode="provider", requires_approval=False)


@pytest.mark.parametrize("field", ["password", "api_key", "nested_secret", "access_token", "private_key", "credential", "handler_path", "shell_command", "module_import", "source_code"])
def test_tool_objects_recursively_reject_secrets_and_executable_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        ToolDefinitionCreate(key="email.send", display_name="Send", description="x", category="email", risk_level="low", execution_mode="provider", metadata={"nested": {field: "unsafe"}})


def test_tool_objects_must_be_json_objects_and_update_is_nonempty() -> None:
    with pytest.raises(ValidationError):
        ToolDefinitionCreate(key="email.send", display_name="Send", description="x", category="email", risk_level="low", execution_mode="provider", input_schema=["not-object"])
    with pytest.raises(ValidationError):
        ToolDefinitionUpdate()


def test_runtime_descriptor_registry_is_exact_and_duplicate_safe() -> None:
    registry = RuntimeToolRegistry()
    descriptor = RuntimeToolDescriptor(key="email.send", implementation_name="Trusted email adapter", execution_mode="provider")
    registry.register(descriptor)
    assert registry.get("email.send") is descriptor
    assert registry.get("email.read") is None
    with pytest.raises(ValueError):
        registry.register(descriptor)
    with pytest.raises(ValueError):
        registry.get("email.*")


def test_runtime_descriptor_contains_no_import_loading_contract() -> None:
    fields = RuntimeToolDescriptor.__dataclass_fields__
    assert set(fields) == {"key", "implementation_name", "execution_mode", "callable_ref"}
    assert not {"import_path", "module", "shell_command", "source_code"}.intersection(fields)


def test_tool_registry_models_enforce_company_and_agent_integrity() -> None:
    grant_fks = {constraint.name: (tuple(constraint.column_keys), tuple(element.target_fullname for element in constraint.elements)) for constraint in AgentToolGrant.__table__.foreign_key_constraints}
    assert grant_fks["fk_agent_tool_grants_company_agent"] == (("company_id", "agent_id"), ("agents.company_id", "agents.id"))
    assert grant_fks["fk_agent_tool_grants_company_tool"] == (("company_id", "tool_definition_id"), ("company_tools.company_id", "company_tools.tool_definition_id"))
    assert any(constraint.name == "uq_company_tools_company_tool" for constraint in CompanyTool.__table__.constraints)
    active = next(index for index in AgentToolGrant.__table__.indexes if index.name == "uq_agent_tool_grants_active")
    assert active.unique and "active" in str(active.dialect_options["postgresql"]["where"])
    assert all(fk.ondelete == "RESTRICT" for model in (ToolDefinition, CompanyTool, AgentToolGrant) for fk in model.__table__.foreign_keys)


def test_tool_role_matrix_preserves_read_and_manage_boundaries() -> None:
    assert role_has_permission("owner", CompanyPermission.TOOLS_MANAGE)
    assert role_has_permission("admin", CompanyPermission.TOOLS_MANAGE)
    assert role_has_permission("operator", CompanyPermission.TOOLS_READ)
    assert role_has_permission("viewer", CompanyPermission.TOOLS_READ)
    assert not role_has_permission("operator", CompanyPermission.TOOLS_MANAGE)
    assert not role_has_permission("viewer", CompanyPermission.TOOLS_MANAGE)


@pytest.mark.parametrize("operation", ["enable_company_tool", "disable_company_tool"])
def test_system_company_tool_mutations_require_superuser(operation: str) -> None:
    definition = tool(is_system=True)
    repository = SimpleNamespace(get_tool=lambda tool_id, for_update=False: definition)
    service = ToolRegistryService(repository, SimpleNamespace(), SimpleNamespace())
    with pytest.raises(ToolAuthorizationError):
        getattr(service, operation)(company_id=uuid4(), tool_id=definition.id, actor=SimpleNamespace(id=uuid4(), is_superuser=False))


def test_tool_audit_actions_are_normalized() -> None:
    actions = {"tool_definition.created", "tool_definition.updated", "tool_definition.activated", "tool_definition.deactivated", "tool_definition.deprecated", "company_tool.enabled", "company_tool.disabled", "agent_tool.granted", "agent_tool.revoked"}
    assert {AuditAction(action).value for action in actions} == actions


def test_approval_action_is_derived_from_persisted_tool_and_identity() -> None:
    item = agent()
    identity = AuthenticatedAgent(item, credential(item), ())
    action = tool_authorization_action(identity, tool())
    assert action.action_type == "tool.execute.email.send"
    assert action.tool_identifier == "email.send"
    assert action.actor_agent_id == item.id and action.company_id == item.company_id
    assert "*" not in action.action_type


class EffectiveRepository:
    def __init__(self, item, rows, company=None):
        self.item = item
        self.rows = rows
        self.company = company or SimpleNamespace(id=item.company_id, is_active=True, status="active")
        self.calls = []

    def get_agent(self, *, company_id, agent_id):
        return self.item if (company_id, agent_id) == (self.item.company_id, self.item.id) else None

    def get_company(self, company_id):
        return self.company if company_id == self.company.id else None

    def list_effective_grants(self, *, company_id, agent_id):
        self.calls.append((company_id, agent_id))
        return self.rows


def test_effective_tools_derive_company_agent_and_runtime_registration() -> None:
    item = agent()
    key = credential(item)
    definition = tool()
    grant = SimpleNamespace(id=uuid4())
    repository = EffectiveRepository(item, [(grant, definition)])
    descriptors = RuntimeToolRegistry()
    descriptors.register(RuntimeToolDescriptor(key="email.send", implementation_name="Trusted", execution_mode="provider"))
    service = ToolRegistryService(repository, SimpleNamespace(), SimpleNamespace(), descriptors)
    result = service.effective_tools(AuthenticatedAgent(item, key, ()))
    assert repository.calls == [(item.company_id, item.id)]
    assert len(result) == 1 and result[0].runtime_registered is True


@pytest.mark.parametrize(("agent_status", "credential_status"), [("inactive", "active"), ("revoked", "active"), ("active", "revoked")])
def test_inactive_identity_has_no_effective_tools(agent_status: str, credential_status: str) -> None:
    item = agent(status=agent_status)
    repository = EffectiveRepository(item, [(SimpleNamespace(id=uuid4()), tool())])
    service = ToolRegistryService(repository, SimpleNamespace(), SimpleNamespace(), RuntimeToolRegistry())
    assert service.effective_tools(AuthenticatedAgent(item, credential(item, status=credential_status), ())) == []
    assert repository.calls == []


def test_inactive_company_and_expired_credential_have_no_effective_tools() -> None:
    item = agent()
    disabled_company = SimpleNamespace(id=item.company_id, is_active=False, status="inactive")
    repository = EffectiveRepository(item, [(SimpleNamespace(id=uuid4()), tool())], company=disabled_company)
    service = ToolRegistryService(repository, SimpleNamespace(), SimpleNamespace(), RuntimeToolRegistry())
    assert service.effective_tools(AuthenticatedAgent(item, credential(item), ())) == []

    active_repository = EffectiveRepository(item, [(SimpleNamespace(id=uuid4()), tool())])
    expired = credential(item, expires_at=NOW.replace(year=NOW.year - 1))
    expired_service = ToolRegistryService(active_repository, SimpleNamespace(), SimpleNamespace(), RuntimeToolRegistry())
    assert expired_service.effective_tools(AuthenticatedAgent(item, expired, ())) == []


class EffectiveApiService:
    def __init__(self, result):
        self.result = result

    def effective_tools(self, _identity):
        return self.result

    def effective_tool(self, _identity, key):
        return next((item for item in self.result if item.tool.key == key), None)


def test_internal_tool_api_uses_authenticated_identity_and_hides_missing_tools() -> None:
    item = agent()
    identity = AuthenticatedAgent(item, credential(item), ())
    app.dependency_overrides[require_current_agent] = lambda: identity
    app.dependency_overrides[get_tool_registry_service] = lambda: EffectiveApiService([])
    try:
        with TestClient(app) as client:
            listing = client.get("/api/v1/internal/tools", headers={"Authorization": "Bearer test"})
            missing = client.get("/api/v1/internal/tools/email.send", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.clear()
    assert listing.status_code == 200 and listing.json() == {"items": []}
    assert missing.status_code == 404


def test_tool_routes_are_registered_without_unrestricted_execution_endpoint() -> None:
    paths = app.openapi()["paths"]
    expected = {"/api/v1/tools", "/api/v1/tools/{tool_id}", "/api/v1/companies/{company_id}/tools", "/api/v1/companies/{company_id}/agents/{agent_id}/tools", "/api/v1/internal/tools", "/api/v1/internal/tools/{tool_key}"}
    assert expected <= set(paths)
    assert "/api/v1/companies/{company_id}/agent-runtime/tools/{tool_key}/invoke" in paths
    assert not any(path.endswith("/execute") or "tool-execution" in path for path in paths)
    assert all("delete" not in operations for path, operations in paths.items() if "/tools" in path or "/tool-grants" in path)
