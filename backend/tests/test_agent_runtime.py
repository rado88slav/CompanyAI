"""Tests for the safe read-only agent runtime boundary."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.authentication import require_current_administrator
from app.api.dependencies.company_authorization import require_tools_manage, require_tools_read
from app.core.tool_registry import RuntimeToolDescriptor, RuntimeToolRegistry
from app.main import app
from app.models.audit_log import AuditAction
from app.schemas.agent_runtime import AgentRuntimeToolResponse
from app.schemas.company_context import ActiveCompanyContext
from app.schemas.dashboard import DashboardCounts, DashboardReadinessStatus, DashboardServiceStatus, DashboardServiceSummary, DashboardSummaryResponse
from app.services.agent_runtime import AgentRuntimeInputError, AgentRuntimeNotFoundError, AgentRuntimeService, AgentRuntimeUnavailableError, get_agent_runtime_service

NOW = datetime.now(UTC)


def administrator(**overrides):
    values = dict(id=uuid4(), email="admin@example.test", is_superuser=False)
    values.update(overrides)
    return SimpleNamespace(**values)


def context(actor=None, company_id=None):
    company = SimpleNamespace(id=company_id or uuid4(), status="active", is_active=True)
    return ActiveCompanyContext(
        administrator=actor or administrator(),
        company=company,
        membership=SimpleNamespace(role="admin", status="active"),
        is_platform_superuser=False,
    )


def tool_definition(**overrides):
    values = dict(
        id=uuid4(),
        key="dashboard.summary.read",
        display_name="Read dashboard summary",
        description="Return safe dashboard summary.",
        category="dashboard",
        risk_level="low",
        execution_mode="internal",
        requires_approval=False,
        status="active",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def company_tool(**overrides):
    values = dict(id=uuid4(), status="enabled")
    values.update(overrides)
    return SimpleNamespace(**values)


def summary():
    return DashboardSummaryResponse(
        service=DashboardServiceSummary(
            status=DashboardServiceStatus.OK,
            readiness=DashboardReadinessStatus.REACHABLE,
            environment="test",
            version="1.0.0",
        ),
        counts=DashboardCounts(
            provider_connections=1,
            enabled_provider_connections=1,
            provider_credentials=0,
            pending_approvals=0,
            provider_executions=0,
            failed_provider_executions=0,
            audit_events=0,
        ),
        recent_audit_events=[],
    )


class FakeRepository:
    def __init__(self, *, definition=None, availability=None):
        self.definition = definition
        self.availability = availability
        self.created_tools = []
        self.created_company_tools = []

    def list_tools(self, **_filters):
        return [self.definition] if self.definition is not None else []

    def get_tool_by_key(self, key):
        return self.definition if self.definition is not None and self.definition.key == key else None

    def get_company_tool(self, **_filters):
        return self.availability

    def create_tool(self, **values):
        item = tool_definition(**values)
        self.definition = item
        self.created_tools.append(values)
        return item

    def create_company_tool(self, **values):
        item = company_tool(**values)
        self.availability = item
        self.created_company_tools.append(values)
        return item

    def save_company_tool(self, item):
        return item


class FakeAudit:
    def __init__(self):
        self.events = []

    def append_platform_event(self, **values):
        self.events.append(("platform", values))
        return SimpleNamespace(id=uuid4(), created_at=NOW)

    def append_company_event(self, **values):
        self.events.append(("company", values))
        return SimpleNamespace(id=uuid4(), created_at=NOW)


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakeDashboard:
    def __init__(self):
        self.calls = []

    def get_summary(self, *, company_id):
        self.calls.append(company_id)
        return summary()


class FakeEmailCampaigns:
    def list_campaigns(self, *, company_id, limit, offset):
        return [
            SimpleNamespace(
                id=uuid4(),
                company_id=company_id,
                provider_key="local_mock_email",
                external_campaign_id="mock",
                name="Mock campaign",
                status="draft",
                audience_count=1,
                sent_count=0,
                reply_count=0,
                bounce_count=0,
                created_at=NOW,
                updated_at=NOW,
                model_dump=lambda mode="json": {
                    "id": str(uuid4()),
                    "company_id": str(company_id),
                    "provider_key": "local_mock_email",
                    "external_campaign_id": "mock",
                    "name": "Mock campaign",
                    "status": "draft",
                    "audience_count": 1,
                    "sent_count": 0,
                    "reply_count": 0,
                    "bounce_count": 0,
                    "created_at": NOW.isoformat(),
                    "updated_at": NOW.isoformat(),
                },
            )
        ], 1


def service(*, definition=None, availability=None, descriptors=None):
    return AgentRuntimeService(
        tool_repository=FakeRepository(definition=definition, availability=availability),
        dashboard=FakeDashboard(),
        email_campaigns=FakeEmailCampaigns(),
        audit=FakeAudit(),
        session=FakeSession(),
        descriptors=descriptors or RuntimeToolRegistry(),
    )


def registered_descriptors():
    registry = RuntimeToolRegistry()
    registry.register(
        RuntimeToolDescriptor(
            key="dashboard.summary.read",
            implementation_name="Read dashboard summary",
            execution_mode="internal",
        )
    )
    return registry


def test_agent_runtime_lists_only_active_registered_internal_tools() -> None:
    runtime = service(
        definition=tool_definition(),
        availability=company_tool(),
        descriptors=registered_descriptors(),
    )
    items = runtime.list_tools(company_id=uuid4())
    assert len(items) == 1
    assert items[0].key == "dashboard.summary.read"
    assert items[0].runtime_registered is True
    assert items[0].company_enabled is True


def test_agent_runtime_requires_registered_active_enabled_tool() -> None:
    with pytest.raises(AgentRuntimeNotFoundError):
        service(definition=tool_definition(), availability=company_tool()).invoke_tool(
            company_id=uuid4(),
            tool_key="dashboard.summary.read",
            input_data={},
            actor=administrator(),
        )
    with pytest.raises(AgentRuntimeUnavailableError):
        service(definition=tool_definition(status="inactive"), availability=company_tool(), descriptors=registered_descriptors()).invoke_tool(
            company_id=uuid4(),
            tool_key="dashboard.summary.read",
            input_data={},
            actor=administrator(),
        )
    with pytest.raises(AgentRuntimeUnavailableError):
        service(definition=tool_definition(), availability=None, descriptors=registered_descriptors()).invoke_tool(
            company_id=uuid4(),
            tool_key="dashboard.summary.read",
            input_data={},
            actor=administrator(),
        )


def test_agent_runtime_invokes_dashboard_summary_and_audits_safely() -> None:
    runtime = service(
        definition=tool_definition(),
        availability=company_tool(),
        descriptors=registered_descriptors(),
    )
    result = runtime.invoke_tool(
        company_id=uuid4(),
        tool_key="dashboard.summary.read",
        input_data={},
        actor=administrator(),
    )
    assert result.status == "succeeded"
    assert result.result["service"]["status"] == "ok"
    assert "token" not in str(result.model_dump(mode="json")).lower()


def test_agent_runtime_invokes_mock_email_campaign_listing() -> None:
    registry = registered_descriptors()
    registry.register(
        RuntimeToolDescriptor(
            key="email.campaigns.list",
            implementation_name="List mock email campaigns",
            execution_mode="internal",
        )
    )
    runtime = service(
        definition=tool_definition(
            key="email.campaigns.list",
            display_name="List mock email campaigns",
            category="email",
        ),
        availability=company_tool(),
        descriptors=registry,
    )
    result = runtime.invoke_tool(
        company_id=uuid4(),
        tool_key="email.campaigns.list",
        input_data={},
        actor=administrator(),
    )
    assert result.status == "succeeded"
    assert result.result["items"][0]["provider_key"] == "local_mock_email"
    assert "secret" not in str(result.model_dump(mode="json")).lower()


def test_agent_runtime_rejects_unexpected_input() -> None:
    runtime = service(
        definition=tool_definition(),
        availability=company_tool(),
        descriptors=registered_descriptors(),
    )
    with pytest.raises(AgentRuntimeInputError):
        runtime.invoke_tool(
            company_id=uuid4(),
            tool_key="dashboard.summary.read",
            input_data={"unexpected": "value"},
            actor=administrator(),
        )


def test_development_bootstrap_is_idempotent_and_audited() -> None:
    actor = administrator(is_superuser=True)
    runtime = service(definition=None, availability=None, descriptors=registered_descriptors())
    result = runtime.bootstrap_dashboard_summary_tool(
        company_id=uuid4(),
        actor=actor,
        app_environment="development",
    )
    assert result.tool_key == "dashboard.summary.read"
    assert result.company_enabled is True
    with pytest.raises(AgentRuntimeUnavailableError):
        runtime.bootstrap_dashboard_summary_tool(
            company_id=uuid4(),
            actor=actor,
            app_environment="production",
        )
    email_tool = runtime.bootstrap_email_campaigns_tool(
        company_id=uuid4(),
        actor=actor,
        app_environment="development",
    )
    assert email_tool.tool_key == "email.campaigns.list"


class ApiService:
    def list_tools(self, *, company_id):
        return [
            AgentRuntimeToolResponse(
                key="dashboard.summary.read",
                display_name="Read dashboard summary",
                description="Return safe dashboard summary.",
                category="dashboard",
                risk_level="low",
                requires_approval=False,
                runtime_registered=True,
                company_enabled=True,
            )
        ]

    def invoke_tool(self, **_values):
        return SimpleNamespace(
            tool_key="dashboard.summary.read",
            status="succeeded",
            executed_at=NOW,
            audit_event_id=uuid4(),
            result=summary().model_dump(mode="json"),
        )

    def bootstrap_dashboard_summary_tool(self, **_values):
        return SimpleNamespace(
            tool_id=uuid4(),
            company_tool_id=uuid4(),
            tool_key="dashboard.summary.read",
            company_enabled=True,
        )


def test_agent_runtime_api_uses_company_context_and_typed_responses() -> None:
    company_id = uuid4()
    actor = administrator()
    app.dependency_overrides[require_current_administrator] = lambda: actor
    app.dependency_overrides[require_tools_read] = lambda: context(actor, company_id)
    app.dependency_overrides[require_tools_manage] = lambda: context(actor, company_id)
    app.dependency_overrides[get_agent_runtime_service] = lambda: ApiService()
    try:
        with TestClient(app) as client:
            listing = client.get(
                f"/api/v1/companies/{company_id}/agent-runtime/tools",
                headers={"Authorization": "Bearer test", "X-Company-ID": str(company_id)},
            )
            invocation = client.post(
                f"/api/v1/companies/{company_id}/agent-runtime/tools/dashboard.summary.read/invoke",
                json={"input": {}},
                headers={"Authorization": "Bearer test", "X-Company-ID": str(company_id)},
            )
    finally:
        app.dependency_overrides.clear()
    assert listing.status_code == 200
    assert listing.json()["items"][0]["key"] == "dashboard.summary.read"
    assert invocation.status_code == 200
    assert invocation.json()["status"] == "succeeded"


def test_agent_runtime_audit_action_is_normalized_and_routes_registered() -> None:
    assert AuditAction.AGENT_TOOL_INVOKED.value == "agent_tool.invoked"
    paths = app.openapi()["paths"]
    assert "/api/v1/companies/{company_id}/agent-runtime/tools" in paths
    assert "/api/v1/companies/{company_id}/agent-runtime/tools/{tool_key}/invoke" in paths
