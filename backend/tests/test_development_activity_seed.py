"""Tests for deterministic development-only Activity Center seed data."""

from types import SimpleNamespace
from uuid import uuid4

from app.models.audit_log import AuditLog
from app.services.development_activity_seed import (
    DEVELOPMENT_ACTIVITY_SEEDS,
    seed_development_activity,
)


class FakeSeedSession:
    """Tiny session fake for idempotent seed behavior."""

    def __init__(self, company_id):
        self.company = SimpleNamespace(id=company_id, slug="company-test")
        self.events: dict[object, AuditLog] = {}
        self.commit_count = 0

    def scalar(self, _statement):
        return self.company

    def get(self, _model, event_id):
        return self.events.get(event_id)

    def add(self, event):
        self.events[event.id] = event

    def commit(self):
        self.commit_count += 1


def test_development_activity_seed_is_deterministic_and_idempotent() -> None:
    session = FakeSeedSession(uuid4())

    inserted, skipped = seed_development_activity(session)  # type: ignore[arg-type]
    second_inserted, second_skipped = seed_development_activity(session)  # type: ignore[arg-type]

    assert inserted == len(DEVELOPMENT_ACTIVITY_SEEDS)
    assert skipped == 0
    assert second_inserted == 0
    assert second_skipped == len(DEVELOPMENT_ACTIVITY_SEEDS)
    assert len(session.events) == len(DEVELOPMENT_ACTIVITY_SEEDS)
    assert session.commit_count == 2


def test_development_activity_seed_is_company_scoped() -> None:
    first_company_id = uuid4()
    second_company_id = uuid4()
    first = FakeSeedSession(first_company_id)
    second = FakeSeedSession(second_company_id)

    seed_development_activity(first)  # type: ignore[arg-type]
    seed_development_activity(second)  # type: ignore[arg-type]

    assert set(first.events) != set(second.events)
    assert {event.company_id for event in first.events.values()} == {first_company_id}
    assert {event.company_id for event in second.events.values()} == {second_company_id}


def test_development_activity_seed_contains_only_safe_details() -> None:
    session = FakeSeedSession(uuid4())
    seed_development_activity(session)  # type: ignore[arg-type]

    forbidden_parts = {"token", "secret", "password", "hash", "credential", "api_key"}
    actions = {event.action for event in session.events.values()}

    assert {
        "agent_tool.invoked",
        "approval_request.created",
        "approval_request.approved",
        "provider_connection.activated",
        "email.imported",
        "company.updated",
        "administrator.authenticated",
    } <= actions
    for event in session.events.values():
        assert event.scope == "company"
        assert event.actor_type == "system"
        assert event.details["development_only"] is True
        for key in event.details:
            assert not any(part in key for part in forbidden_parts)
