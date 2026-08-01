"""Focused tests for the safe preview Agent Manager."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.schemas.agent_manager import AgentManagerCreateFromTemplateRequest, AgentManagerInstructionsUpdate, AgentPreviewTaskRequest
from app.services.agent_manager import AgentManagerDeniedError, AgentManagerService, PreviewRuntimeOutputError


class FakeAgentRepo:
    def __init__(self) -> None:
        self.agents: dict[UUID, SimpleNamespace] = {}
        self.permissions: dict[UUID, list[SimpleNamespace]] = {}

    def list_agents(self, *, company_id: UUID, status, agent_type, search, limit, offset):
        return [item for item in self.agents.values() if item.company_id == company_id][offset: offset + limit]

    def count_agents(self, *, company_id: UUID, status, agent_type, search):
        return len([item for item in self.agents.values() if item.company_id == company_id])

    def get_by_slug(self, *, company_id: UUID, slug: str):
        return next((item for item in self.agents.values() if item.company_id == company_id and item.slug == slug), None)

    def create_agent(self, **values):
        now = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
        item = SimpleNamespace(id=uuid4(), created_at=now, updated_at=now, auth_version=1, revoked_at=None, revocation_reason=None, **values)
        self.agents[item.id] = item
        return item

    def get_agent(self, *, company_id: UUID, agent_id: UUID, for_update: bool = False):
        item = self.agents.get(agent_id)
        if item is None or item.company_id != company_id:
            return None
        return item

    def save_agent(self, item):
        item.updated_at = datetime(2026, 8, 1, 10, 5, tzinfo=UTC)
        self.agents[item.id] = item
        return item

    def create_permission(self, **values):
        item = SimpleNamespace(id=uuid4(), status="active", created_at=datetime(2026, 8, 1, 10, 1, tzinfo=UTC), **values)
        self.permissions.setdefault(item.agent_id, []).append(item)
        return item

    def list_permissions(self, *, company_id: UUID, agent_id: UUID, active_only: bool = False):
        items = self.permissions.get(agent_id, [])
        if active_only:
            return [item for item in items if item.status == "active"]
        return items


class FakeAudit:
    def __init__(self) -> None:
        self.events = []

    def append_company_event(self, **kwargs):
        event = SimpleNamespace(id=uuid4(), created_at=datetime(2026, 8, 1, 10, 2, tzinfo=UTC), **kwargs)
        self.events.append(kwargs)
        return event


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeAuthorizer:
    def evaluate(self, action):
        return SimpleNamespace(status="approval_required", reason_code="no_matching_grant", effective_risk=action.risk_level, approval_request_id=None, policy_id=None)


class BadRuntime:
    def run(self, *, task):
        return {"not": "a typed proposal"}


def make_service(runtime=None):
    repo = FakeAgentRepo()
    audit = FakeAudit()
    session = FakeSession()
    service = AgentManagerService(agents=repo, audit=audit, authorizer=FakeAuthorizer(), session=session, runtime=runtime)
    return service, repo, audit, session


def create_active_agent(service: AgentManagerService, repo: FakeAgentRepo, company_id: UUID, actor):
    agent = service.create_from_template(company_id=company_id, data=AgentManagerCreateFromTemplateRequest(), actor=actor)
    repo.agents[agent.id].status = "active"
    return agent


def test_template_registration_and_prompt_are_safe() -> None:
    service, repo, _audit, _session = make_service()
    company_id = uuid4()
    actor = SimpleNamespace(id=uuid4())

    template = service.templates()[0]
    agent = service.create_from_template(company_id=company_id, data=AgentManagerCreateFromTemplateRequest(company_instructions="Stay conservative."), actor=actor)
    prompt = service.prompt_preview(company_id=company_id, agent_id=agent.id)

    assert template.template_id == "email_operations_preview_agent"
    assert agent.status == "inactive"
    assert "agent.preview.email_schedule" in agent.permissions
    assert "Stay conservative." in prompt.prompt_text
    assert "password" not in prompt.prompt_text.lower()
    assert repo.get_agent(company_id=uuid4(), agent_id=agent.id) is None


def test_secret_like_instruction_and_payload_are_rejected() -> None:
    with pytest.raises(ValidationError):
        AgentManagerCreateFromTemplateRequest(company_instructions="Use this password: no.")
    with pytest.raises(ValidationError):
        AgentManagerInstructionsUpdate(company_instructions="credential value")
    with pytest.raises(ValidationError):
        AgentPreviewTaskRequest(task_key="classify_unsubscribe", synthetic_reply="access token abc")


def test_preview_task_returns_structured_proposal_and_audit() -> None:
    service, repo, audit, session = make_service()
    company_id = uuid4()
    actor = SimpleNamespace(id=uuid4())
    agent = create_active_agent(service, repo, company_id, actor)

    result = service.run_task(
        company_id=company_id,
        agent_id=agent.id,
        data=AgentPreviewTaskRequest(task_key="draft_interested_follow_up", synthetic_reply="Sounds interesting."),
        actor=actor,
    )

    assert result.status == "previewed"
    assert result.proposal.proposal_type == "draft_reply"
    assert result.authorization.status == "approval_required"
    assert result.provider_execution_created is False
    assert result.external_action_taken is False
    assert audit.events[-1]["action"] == "agent_manager.task_previewed"
    assert session.commits >= 2


def test_forbidden_send_is_denied_without_provider_execution() -> None:
    service, repo, audit, _session = make_service()
    company_id = uuid4()
    actor = SimpleNamespace(id=uuid4())
    agent = create_active_agent(service, repo, company_id, actor)

    result = service.run_task(company_id=company_id, agent_id=agent.id, data=AgentPreviewTaskRequest(task_key="attempt_forbidden_send"), actor=actor)

    assert result.status == "denied"
    assert result.authorization.status == "blocked"
    assert result.authorization.reason_code == "forbidden_by_agent_template"
    assert result.external_action_taken is False
    assert audit.events[-1]["action"] == "agent_manager.task_denied"


def test_inactive_agent_and_malformed_runtime_output_are_rejected() -> None:
    service, _repo, _audit, _session = make_service()
    company_id = uuid4()
    actor = SimpleNamespace(id=uuid4())
    agent = service.create_from_template(company_id=company_id, data=AgentManagerCreateFromTemplateRequest(), actor=actor)
    with pytest.raises(AgentManagerDeniedError):
        service.run_task(company_id=company_id, agent_id=agent.id, data=AgentPreviewTaskRequest(task_key="preview_next_email_actions"), actor=actor)

    bad_service, repo, _audit, _session = make_service(runtime=BadRuntime())
    active = create_active_agent(bad_service, repo, company_id, actor)
    with pytest.raises(PreviewRuntimeOutputError):
        bad_service.run_task(company_id=company_id, agent_id=active.id, data=AgentPreviewTaskRequest(task_key="preview_next_email_actions"), actor=actor)
