"""Isolated tests for exact safety bootstrap verification and legacy repair."""

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.cli import bootstrap_authorization_safety as bootstrap


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None: self.commits += 1
    def rollback(self) -> None: self.rollbacks += 1


class FakePolicies:
    def __init__(self, items: list) -> None:
        self.items = list(items)
        self.created: list = []
        self.revoked: list = []

    def create_policy(self, **values):
        policy = SimpleNamespace(id=uuid4(), **values, revoked_at=None, revoked_by_administrator_id=None, revocation_reason=None)
        self.items.append(policy); self.created.append(policy)
        return policy

    def revoke_policy(self, policy, *, actor_id, revoked_at, reason):
        policy.status = "revoked"; policy.revoked_at = revoked_at
        policy.revoked_by_administrator_id = actor_id; policy.revocation_reason = reason
        self.revoked.append(policy); return policy


class FakeAudit:
    def __init__(self) -> None:
        self.events = [{"action": "authorization_policy.created", "historical": True}]

    def append_platform_event(self, **event): self.events.append(event)
    def append_company_event(self, **event): self.events.append(event)


def make_policy(definition, *, company_id=None, legacy=False, **overrides):
    policy_scope = "platform" if company_id is None else "company"
    values = bootstrap._expected_definition(definition, policy_scope=policy_scope, company_id=company_id)
    if legacy:
        values["scope_type"], values["scope_id"] = bootstrap._legacy_scope(policy_scope=policy_scope, company_id=company_id)
    values.update(overrides)
    return SimpleNamespace(id=uuid4(), created_by_administrator_id=uuid4(), valid_from=None, **values)


def setup_isolated(monkeypatch, items):
    session = FakeSession(); policies = FakePolicies(items); audit = FakeAudit()
    def active(_session, *, policy_scope, company_id, action_type):
        return [item for item in policies.items if item.status == "active" and item.policy_scope == policy_scope and item.company_id == company_id and item.action_type == action_type]
    monkeypatch.setattr(bootstrap, "_active_policies", active)
    return session, policies, audit


def run(session, policies, audit, *, company_id=None, repair=False):
    return bootstrap.run_bootstrap(session=session, administrator_id=uuid4(), company_id=company_id, platform_defaults=company_id is None, repair_legacy_scope=repair, policies=policies, audit=audit)


def test_normal_bootstrap_accepts_exact_definitions_without_mutation(monkeypatch) -> None:
    items = [make_policy(item) for item in bootstrap.SAFETY_DEFAULTS]
    session, policies, audit = setup_isolated(monkeypatch, items)
    summary = run(session, policies, audit)
    assert summary.verified == summary.exact_noops == 6
    assert not policies.created and not policies.revoked
    assert len(audit.events) == 1 and session.commits == 1


def test_normal_bootstrap_rejects_platform_legacy_scope(monkeypatch) -> None:
    session, policies, audit = setup_isolated(monkeypatch, [make_policy(bootstrap.SAFETY_DEFAULTS[0], legacy=True)])
    with pytest.raises(SystemExit, match="scope_type"):
        run(session, policies, audit)
    assert session.commits == 0 and session.rollbacks == 1 and not policies.revoked


@pytest.mark.parametrize(("field", "value"), [
    ("source_type", "manual"), ("subject_type", "administrator"),
    ("subject_administrator_id", pytest.param(uuid4(), id="subject-selector")),
    ("tool_identifier", "extra.tool"), ("campaign_id", pytest.param(uuid4(), id="campaign-selector")),
    ("max_total_actions", 1), ("max_budget_amount", 10),
    ("conditions", {"allowed_weekdays": [1]}), ("risk_level_max", "high"),
])
def test_bootstrap_rejects_every_security_relevant_mismatch(monkeypatch, field, value) -> None:
    policy = make_policy(bootstrap.SAFETY_DEFAULTS[0], **{field: value})
    session, policies, audit = setup_isolated(monkeypatch, [policy])
    with pytest.raises(SystemExit, match=field): run(session, policies, audit, repair=True)
    assert not policies.revoked and session.rollbacks == 1


@pytest.mark.parametrize("company_id", [None, pytest.param(uuid4(), id="company")])
def test_repair_replaces_only_exact_legacy_shape_and_preserves_history(monkeypatch, company_id) -> None:
    original = [make_policy(item, company_id=company_id, legacy=True) for item in bootstrap.SAFETY_DEFAULTS]
    session, policies, audit = setup_isolated(monkeypatch, original)
    historical = deepcopy(audit.events)
    summary = run(session, policies, audit, company_id=company_id, repair=True)
    assert summary.created == summary.legacy_revoked == summary.legacy_replaced == 6
    assert session.commits == 1 and session.rollbacks == 0
    assert all(item.status == "revoked" and item.revocation_reason == bootstrap.LEGACY_REPAIR_REASON for item in original)
    active = [item for item in policies.items if item.status == "active"]
    assert len(active) == 6 and all(item.scope_type == "any" and item.scope_id is None for item in active)
    assert audit.events[:1] == historical
    assert [event["action"] for event in audit.events[1:]].count("authorization_policy.revoked") == 6
    assert [event["action"] for event in audit.events[1:]].count("authorization_policy.created") == 6


def test_repair_is_idempotent_and_normal_bootstrap_after_repair_is_noop(monkeypatch) -> None:
    session, policies, audit = setup_isolated(monkeypatch, [make_policy(item, legacy=True) for item in bootstrap.SAFETY_DEFAULTS])
    run(session, policies, audit, repair=True)
    first_counts = (len(policies.items), len(audit.events))
    repair_again = run(session, policies, audit, repair=True)
    normal_again = run(session, policies, audit, repair=False)
    assert repair_again.exact_noops == normal_again.exact_noops == 6
    assert (len(policies.items), len(audit.events)) == first_counts
    assert len([item for item in policies.items if item.status == "active"]) == 6


def test_multiple_active_policies_refuse_ambiguous_repair(monkeypatch) -> None:
    definition = bootstrap.SAFETY_DEFAULTS[0]
    session, policies, audit = setup_isolated(monkeypatch, [make_policy(definition, legacy=True), make_policy(definition, legacy=True)])
    with pytest.raises(SystemExit, match="Multiple active policies"): run(session, policies, audit, repair=True)
    assert not policies.revoked and session.rollbacks == 1


def test_one_invalid_definition_rolls_back_complete_six_definition_repair(monkeypatch) -> None:
    items = [make_policy(item, legacy=True) for item in bootstrap.SAFETY_DEFAULTS]
    items[-1].source_type = "approval_decision"
    session, policies, audit = setup_isolated(monkeypatch, items)
    with pytest.raises(SystemExit, match="source_type"): run(session, policies, audit, repair=True)
    assert session.commits == 0 and session.rollbacks == 1


def test_bootstrap_never_touches_requests_decisions_or_usages(monkeypatch) -> None:
    session, policies, audit = setup_isolated(monkeypatch, [])
    summary = run(session, policies, audit)
    assert summary.created == 6
    assert all(set(vars(item)).isdisjoint({"approval_request_id", "approval_decision_id", "authorization_usage_id"}) for item in policies.created)
