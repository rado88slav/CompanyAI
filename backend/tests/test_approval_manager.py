"""Focused regression tests for Approval Manager foundations."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.authorization import PolicyScopeType, RiskLevel, resolve_platform_risk
from app.core.company_permissions import CompanyPermission, role_has_permission
from app.main import app
from app.models.approval import ApprovalDecision, ApprovalRequest, AuthorizationPolicy, AuthorizationUsage
from app.models.audit_log import AuditAction
from app.schemas.approval import ApprovalRequestCreate, AuthorizationAction, AuthorizationConditionsV1, AuthorizationLimits, ManualPolicyCreate
from app.schemas.company_context import ActiveCompanyContext
from app.api.dependencies.company_authorization import require_approvals_read, require_authorization_policies_read, require_authorization_usage_read
from app.services.approval_manager import ApprovalManagerService, get_approval_manager_service
from app.services.authorization_evaluator import AuthorizationEvaluatorService, _matches, _specificity
from app.cli.bootstrap_authorization_safety import SAFETY_DEFAULTS


def test_unknown_action_is_high_risk() -> None:
    assert resolve_platform_risk("unregistered.action") is RiskLevel.HIGH


@pytest.mark.parametrize("weekday", [0, 8])
def test_conditions_reject_invalid_weekdays(weekday: int) -> None:
    with pytest.raises(ValidationError): AuthorizationConditionsV1(allowed_weekdays=[weekday])


def test_conditions_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError): AuthorizationConditionsV1(raw_payload={"secret": True})


def test_conditions_validate_iana_timezone() -> None:
    value = AuthorizationConditionsV1(timezone_policy="fixed", fixed_timezone="Europe/Sofia")
    assert value.fixed_timezone == "Europe/Sofia"
    with pytest.raises(ValidationError): AuthorizationConditionsV1(timezone_policy="fixed", fixed_timezone="Invalid/Zone")


def test_budget_requires_currency() -> None:
    with pytest.raises(ValidationError): AuthorizationLimits(max_budget_amount="10")


def test_approval_decisions_are_append_only_models() -> None:
    assert "updated_at" not in ApprovalDecision.__table__.columns


def test_all_real_foreign_keys_restrict_deletion() -> None:
    tables = (ApprovalRequest, ApprovalDecision, AuthorizationPolicy, AuthorizationUsage)
    foreign_keys = [key for model in tables for key in model.__table__.foreign_keys]
    assert foreign_keys
    assert all(key.ondelete == "RESTRICT" for key in foreign_keys)


def test_pending_request_deduplication_is_partial_unique_index() -> None:
    index = next(index for index in ApprovalRequest.__table__.indexes if index.name == "uq_approval_requests_pending_dedup")
    assert index.unique is True
    assert "pending" in str(index.dialect_options["postgresql"]["where"])


def test_usage_has_unique_reservation_and_partial_execution_keys() -> None:
    assert any(constraint.name == "uq_authorization_usages_reservation_key" for constraint in AuthorizationUsage.__table__.constraints)
    execution = next(index for index in AuthorizationUsage.__table__.indexes if index.name == "uq_authorization_usages_execution")
    assert execution.unique is True


def test_company_role_permission_matrix() -> None:
    assert role_has_permission("owner", CompanyPermission.AUTHORIZATION_POLICIES_MANAGE)
    assert role_has_permission("admin", CompanyPermission.APPROVALS_DECIDE)
    assert role_has_permission("operator", CompanyPermission.APPROVALS_REQUEST)
    assert not role_has_permission("operator", CompanyPermission.APPROVALS_DECIDE)
    assert not role_has_permission("viewer", CompanyPermission.APPROVALS_READ)


def test_human_routes_and_agent_auth_registered_but_internal_runtime_routes_absent() -> None:
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/companies/{company_id}/approval-requests",
        "/api/v1/companies/{company_id}/approval-requests/{request_id}/approve",
        "/api/v1/companies/{company_id}/authorization-policies",
        "/api/v1/companies/{company_id}/authorization-usages",
    }
    assert expected <= set(paths)
    assert "/api/v1/internal/agent-auth/token" in paths
    assert "/api/v1/internal/agent-auth/me" in paths
    assert not any("agent-authorization" in path or "authorization/evaluate" in path for path in paths)


def test_action_actor_identity_is_explicit() -> None:
    action = AuthorizationAction(company_id=uuid4(), actor_type="administrator", actor_administrator_id=uuid4(), action_type="metadata.read", scope_type="company", scheduled_for=datetime.now(UTC) + timedelta(minutes=1))
    assert action.actor_agent_id is None


@pytest.mark.parametrize("action", [
    "approval_request.created", "approval_request.cancelled", "approval_request.expired",
    "approval_request.approved", "approval_request.denied", "authorization_policy.created",
    "authorization_policy.revoked", "authorization_usage.reserved",
    "authorization_usage.succeeded", "authorization_usage.failed", "authorization_usage.released",
])
def test_audit_action_is_normalized_and_controlled(action: str) -> None:
    assert AuditAction(action).value == action


def test_policy_contains_required_security_constraints() -> None:
    names = {constraint.name for constraint in AuthorizationPolicy.__table__.constraints}
    assert {"ck_authorization_policies_scope", "ck_authorization_policies_subject", "ck_authorization_policies_effect_mode", "ck_authorization_policies_positive_limits", "ck_authorization_policies_budget_currency", "ck_authorization_policies_revocation"} <= names


def test_request_contains_requester_xor_and_json_constraints() -> None:
    names = {constraint.name for constraint in ApprovalRequest.__table__.constraints}
    assert {"ck_approval_requests_requester_identity", "ck_approval_requests_limits_object", "ck_approval_requests_conditions_object"} <= names


def test_usage_contains_actor_and_lifecycle_constraints() -> None:
    names = {constraint.name for constraint in AuthorizationUsage.__table__.constraints}
    assert {"ck_authorization_usages_actor", "ck_authorization_usages_lifecycle", "ck_authorization_usages_budget_currency"} <= names


class PaginatedRepository:
    def __init__(self, items: list, total: int) -> None:
        self.items = items
        self.total = total
        self.list_call: dict | None = None
        self.count_call: dict | None = None

    def _list(self, kwargs: dict) -> list:
        self.list_call = kwargs
        return self.items

    def _count(self, kwargs: dict) -> int:
        self.count_call = kwargs
        return self.total

    def list_requests(self, **kwargs): return self._list(kwargs)
    def count_requests(self, *, company_id, requester_administrator_id, status, action_type, tool_identifier, risk_level, campaign_id): return self._count(locals() | {})
    def list_policies(self, **kwargs): return self._list(kwargs)
    def count_policies(self, *, company_id, status, effect, action_type, tool_identifier, campaign_id): return self._count(locals() | {})
    def list_usages(self, **kwargs): return self._list(kwargs)
    def count_usages(self, *, company_id, status, action_type, campaign_id): return self._count(locals() | {})


def _pagination_service(approvals, authorizations) -> ApprovalManagerService:
    return ApprovalManagerService(approvals, authorizations, SimpleNamespace(), SimpleNamespace())  # type: ignore[arg-type]


@pytest.mark.parametrize("collection", ["requests", "policies", "usages"])
def test_service_separates_filters_from_pagination(collection: str) -> None:
    company_id = uuid4()
    actor = SimpleNamespace(id=uuid4())
    repository = PaginatedRepository(["selected-page-item"], 7)
    service = _pagination_service(repository, repository)
    if collection == "requests":
        items, total = service.list_requests(company_id=company_id, actor=actor, own_only=False, requester_administrator_id=None, status="pending", action_type="metadata.read", tool_identifier="crm", risk_level="low", campaign_id=None, limit=1, offset=2)
    elif collection == "policies":
        items, total = service.list_policies(company_id=company_id, status="active", effect="allow", action_type="metadata.read", tool_identifier="crm", campaign_id=None, limit=1, offset=2)
    else:
        items, total = service.list_usages(company_id=company_id, status="reserved", action_type="metadata.read", campaign_id=None, limit=1, offset=2)
    assert items == ["selected-page-item"] and total == 7
    assert repository.list_call is not None and repository.count_call is not None
    assert repository.list_call["limit"] == 1 and repository.list_call["offset"] == 2
    list_filters = {key: value for key, value in repository.list_call.items() if key not in {"limit", "offset"}}
    count_filters = {key: value for key, value in repository.count_call.items() if key != "self"}
    assert "limit" not in repository.count_call and "offset" not in repository.count_call
    assert count_filters == list_filters


@pytest.mark.parametrize("collection", ["requests", "policies", "usages"])
def test_service_empty_page_preserves_zero_total(collection: str) -> None:
    company_id = uuid4(); actor = SimpleNamespace(id=uuid4())
    repository = PaginatedRepository([], 0); service = _pagination_service(repository, repository)
    if collection == "requests": result = service.list_requests(company_id=company_id, actor=actor, own_only=True, requester_administrator_id=None, status=None, action_type=None, tool_identifier=None, risk_level=None, campaign_id=None, limit=1, offset=9)
    elif collection == "policies": result = service.list_policies(company_id=company_id, status=None, effect=None, action_type=None, tool_identifier=None, campaign_id=None, limit=1, offset=9)
    else: result = service.list_usages(company_id=company_id, status=None, action_type=None, campaign_id=None, limit=1, offset=9)
    assert result == ([], 0)
    assert repository.list_call["limit"] == 1 and repository.list_call["offset"] == 9  # type: ignore[index]


@pytest.mark.parametrize("path,method_name,permission", [
    ("approval-requests", "list_requests", require_approvals_read),
    ("authorization-policies", "list_policies", require_authorization_policies_read),
    ("authorization-usages", "list_usages", require_authorization_usage_read),
])
def test_authenticated_collection_api_forwards_explicit_pagination(path: str, method_name: str, permission) -> None:
    company_id = uuid4(); administrator = SimpleNamespace(id=uuid4(), is_active=True, is_superuser=True)
    context = ActiveCompanyContext(administrator=administrator, company=SimpleNamespace(id=company_id), membership=None, is_platform_superuser=True)  # type: ignore[arg-type]

    class Service:
        call: dict | None = None

        def __getattribute__(self, name):
            if name == method_name:
                def listing(**kwargs):
                    self.call = kwargs
                    return [], 0
                return listing
            return object.__getattribute__(self, name)

    fake = Service()
    app.dependency_overrides[permission] = lambda: context
    app.dependency_overrides[get_approval_manager_service] = lambda: fake
    try:
        response = TestClient(app).get(f"/api/v1/companies/{company_id}/{path}?limit=1&offset=4", headers={"Authorization": "Bearer test-token", "X-Company-ID": str(company_id)})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 1, "offset": 4}
    assert fake.call is not None and fake.call["limit"] == 1 and fake.call["offset"] == 4


def _policy(*, company_id=None, scope_type="any", scope_id=None, effect="block", mode="block", action_type="shell.destructive", source_type="bootstrap"):
    return SimpleNamespace(
        id=uuid4(), policy_scope="platform" if company_id is None else "company", company_id=company_id,
        status="active", valid_from=datetime.now(UTC) - timedelta(minutes=1), expires_at=None,
        subject_type="any", subject_administrator_id=None, subject_agent_id=None,
        scope_type=scope_type, scope_id=scope_id, action_type=action_type, tool_identifier=None,
        campaign_id=None, batch_id=None, contact_list_id=None, provider_connection_id=None,
        risk_level_max="critical", conditions={}, effect=effect, authorization_mode=mode,
        source_type=source_type, max_total_actions=None, created_at=datetime.now(UTC),
    )


def _action(*, company_id=None, scope_type="company", scope_id=None, action_type="shell.destructive") -> AuthorizationAction:
    return AuthorizationAction(company_id=company_id or uuid4(), actor_type="administrator", actor_administrator_id=uuid4(), action_type=action_type, risk_level="critical", scope_type=scope_type, scope_id=scope_id)


@pytest.mark.parametrize("scope_type", ["company", "campaign", "batch", "resource"])
def test_any_platform_block_matches_every_concrete_resource_scope(scope_type: str) -> None:
    assert _matches(_policy(), _action(scope_type=scope_type), RiskLevel.CRITICAL, datetime.now(UTC))


def test_company_any_policy_matches_multiple_scopes_but_repository_preserves_company_isolation() -> None:
    company_id, other_company_id = uuid4(), uuid4()
    policy = _policy(company_id=company_id, effect="require_approval", mode="always_require_approval", action_type="email.message.send")

    class Repository:
        def list_matching_policies(self, *, company_id): return [policy] if company_id == policy.company_id else []

    approvals = SimpleNamespace(find_pending_for_action=lambda **kwargs: None)
    evaluator = AuthorizationEvaluatorService(approvals, Repository(), SimpleNamespace(), SimpleNamespace())  # type: ignore[arg-type]
    for scope in ("company", "campaign", "resource"):
        result = evaluator.evaluate(_action(company_id=company_id, scope_type=scope, action_type="email.message.send"))
        assert result.status == "approval_required"
    assert evaluator.evaluate(_action(company_id=other_company_id, scope_type="campaign", action_type="email.message.send")).reason_code == "no_matching_grant"


def test_concrete_scope_type_and_id_remain_exact() -> None:
    scope_id = uuid4()
    policy = _policy(scope_type="campaign", scope_id=scope_id)
    assert _matches(policy, _action(scope_type="campaign", scope_id=scope_id), RiskLevel.CRITICAL, datetime.now(UTC))
    assert not _matches(policy, _action(scope_type="batch", scope_id=scope_id), RiskLevel.CRITICAL, datetime.now(UTC))
    assert not _matches(policy, _action(scope_type="campaign", scope_id=uuid4()), RiskLevel.CRITICAL, datetime.now(UTC))


def test_any_block_cannot_be_bypassed_by_allow_or_superuser_actor() -> None:
    company_id = uuid4(); block = _policy(); allow = _policy(company_id=company_id, scope_type="company", effect="allow", mode="allow_within_limits", source_type="manual")
    repository = SimpleNamespace(list_matching_policies=lambda **kwargs: [allow, block])
    evaluator = AuthorizationEvaluatorService(SimpleNamespace(), repository, SimpleNamespace(), SimpleNamespace())  # type: ignore[arg-type]
    assert evaluator.evaluate(_action(company_id=company_id)).status == "blocked"


def test_any_always_require_cannot_be_bypassed_by_reusable_allow() -> None:
    company_id = uuid4()
    required = _policy(effect="require_approval", mode="always_require_approval", action_type="email.message.send")
    allow = _policy(company_id=company_id, scope_type="company", effect="allow", mode="approve_campaign", action_type="email.message.send", source_type="approval_decision")
    repository = SimpleNamespace(list_matching_policies=lambda **kwargs: [allow, required])
    approvals = SimpleNamespace(find_pending_for_action=lambda **kwargs: None)
    evaluator = AuthorizationEvaluatorService(approvals, repository, SimpleNamespace(), SimpleNamespace())  # type: ignore[arg-type]
    assert evaluator.evaluate(_action(company_id=company_id, action_type="email.message.send")).status == "approval_required"


def test_exact_scope_specificity_precedes_wildcard_and_exact_id_precedes_type() -> None:
    wildcard = _policy(scope_type="any")
    exact_type = _policy(scope_type="campaign")
    exact_id = _policy(scope_type="campaign", scope_id=uuid4())
    assert sorted([wildcard, exact_id, exact_type], key=_specificity) == [exact_id, exact_type, wildcard]


def test_wildcard_scope_schema_boundaries() -> None:
    with pytest.raises(ValidationError):
        ManualPolicyCreate(effect="block", authorization_mode="block", scope_type="any", scope_id=uuid4(), valid_from=datetime.now(UTC))
    with pytest.raises(ValidationError):
        AuthorizationAction(company_id=uuid4(), actor_type="system", action_type="metadata.read", scope_type="any")
    with pytest.raises(ValidationError):
        ApprovalRequestCreate(authorization_mode="ask_every_time", action_type="metadata.read", risk_level="low", scope_type="any")


def test_every_bootstrap_definition_uses_reserved_any_scope() -> None:
    assert PolicyScopeType.ANY.value == "any"
    assert all(item.scope_type == PolicyScopeType.ANY.value and item.scope_id is None for item in SAFETY_DEFAULTS)
