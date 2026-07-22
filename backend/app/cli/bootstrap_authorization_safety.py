"""Explicit, idempotent authorization safety bootstrap and legacy repair."""

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.authorization import PolicyScopeType
from app.db.session import SessionFactory
from app.models.approval import AuthorizationPolicy
from app.models.audit_log import AuditAction
from app.repositories.administrator import AdministratorRepository
from app.repositories.approval import AuthorizationRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.company import CompanyRepository
from app.services.audit_log import AuditLogService

LEGACY_REPAIR_REASON = "Replaced legacy bootstrap company scope with wildcard any scope."


@dataclass(frozen=True)
class SafetyDefault:
    action_type: str
    effect: str
    authorization_mode: str
    scope_type: str = PolicyScopeType.ANY.value
    scope_id: None = None


@dataclass
class BootstrapSummary:
    verified: int = 0
    created: int = 0
    legacy_revoked: int = 0
    legacy_replaced: int = 0
    exact_noops: int = 0


SAFETY_DEFAULTS = (
    SafetyDefault("shell.destructive", "block", "block"),
    SafetyDefault("credential.mutate", "require_approval", "always_require_approval"),
    SafetyDefault("permission.change", "require_approval", "always_require_approval"),
    SafetyDefault("role.change", "require_approval", "always_require_approval"),
    SafetyDefault("owner.change", "require_approval", "always_require_approval"),
    SafetyDefault("external.bulk_communication", "require_approval", "ask_every_time"),
)

SECURITY_FIELDS = (
    "policy_scope", "company_id", "effect", "authorization_mode", "source_type",
    "source_approval_request_id", "source_approval_decision_id", "subject_type",
    "subject_administrator_id", "subject_agent_id", "scope_type", "scope_id",
    "action_type", "tool_identifier", "campaign_id", "batch_id", "contact_list_id",
    "provider_connection_id", "risk_level_max", "status", "max_total_actions",
    "max_hourly_actions", "max_daily_actions", "max_followups_per_target",
    "max_budget_amount", "budget_currency", "expires_at", "conditions_schema_version",
    "conditions", "revoked_at", "revoked_by_administrator_id", "revocation_reason",
)


def _expected_definition(definition: SafetyDefault, *, policy_scope: str, company_id: UUID | None) -> dict[str, Any]:
    return {
        "policy_scope": policy_scope, "company_id": company_id,
        "effect": definition.effect, "authorization_mode": definition.authorization_mode,
        "source_type": "bootstrap", "source_approval_request_id": None,
        "source_approval_decision_id": None, "subject_type": "any",
        "subject_administrator_id": None, "subject_agent_id": None,
        "scope_type": definition.scope_type, "scope_id": definition.scope_id,
        "action_type": definition.action_type, "tool_identifier": None,
        "campaign_id": None, "batch_id": None, "contact_list_id": None,
        "provider_connection_id": None, "risk_level_max": "critical", "status": "active",
        "max_total_actions": None, "max_hourly_actions": None, "max_daily_actions": None,
        "max_followups_per_target": None, "max_budget_amount": None,
        "budget_currency": None, "expires_at": None, "conditions_schema_version": 1,
        "conditions": {}, "revoked_at": None, "revoked_by_administrator_id": None,
        "revocation_reason": None,
    }


def _mismatched_fields(policy: AuthorizationPolicy, expected: dict[str, Any]) -> list[str]:
    return sorted(field for field in SECURITY_FIELDS if getattr(policy, field) != expected[field])


def _legacy_scope(*, policy_scope: str, company_id: UUID | None) -> tuple[str, UUID | None]:
    return "company", None if policy_scope == "platform" else company_id


def _is_exact_legacy(policy: AuthorizationPolicy, expected: dict[str, Any], *, policy_scope: str, company_id: UUID | None) -> bool:
    mismatches = set(_mismatched_fields(policy, expected))
    return mismatches <= {"scope_type", "scope_id"} and (policy.scope_type, policy.scope_id) == _legacy_scope(policy_scope=policy_scope, company_id=company_id)


def _active_policies(session: Session, *, policy_scope: str, company_id: UUID | None, action_type: str) -> list[AuthorizationPolicy]:
    company_filter = AuthorizationPolicy.company_id.is_(None) if company_id is None else AuthorizationPolicy.company_id == company_id
    statement = select(AuthorizationPolicy).where(AuthorizationPolicy.policy_scope == policy_scope, company_filter, AuthorizationPolicy.action_type == action_type, AuthorizationPolicy.status == "active")
    return list(session.scalars(statement).all())


def _append_policy_event(audit: AuditLogService, *, company_id: UUID | None, actor_id: UUID, action: str, policy: AuthorizationPolicy, details: dict[str, Any]) -> None:
    if company_id is None:
        audit.append_platform_event(actor_administrator_id=actor_id, action=action, resource_type="authorization_policy", resource_id=policy.id, details=details)
    else:
        audit.append_company_event(company_id=company_id, actor_administrator_id=actor_id, action=action, resource_type="authorization_policy", resource_id=policy.id, details=details)


def run_bootstrap(*, session: Session, administrator_id: UUID, company_id: UUID | None, platform_defaults: bool, repair_legacy_scope: bool, policies: AuthorizationRepository, audit: AuditLogService) -> BootstrapSummary:
    """Verify/create exact definitions or atomically replace only approved legacy scopes."""

    policy_scope = "platform" if platform_defaults else "company"
    summary = BootstrapSummary()
    try:
        for definition in SAFETY_DEFAULTS:
            expected = _expected_definition(definition, policy_scope=policy_scope, company_id=company_id)
            active = _active_policies(session, policy_scope=policy_scope, company_id=company_id, action_type=definition.action_type)
            if len(active) > 1:
                raise SystemExit(f"Multiple active policies for {definition.action_type}; refusing ambiguous bootstrap or repair.")
            if active:
                existing = active[0]
                mismatches = _mismatched_fields(existing, expected)
                if not mismatches:
                    summary.verified += 1; summary.exact_noops += 1
                    continue
                if not repair_legacy_scope or not _is_exact_legacy(existing, expected, policy_scope=policy_scope, company_id=company_id):
                    raise SystemExit(f"Conflicting policy for {definition.action_type}; mismatched fields: {', '.join(mismatches)}. No policies were changed.")
                revoked = policies.revoke_policy(existing, actor_id=administrator_id, revoked_at=datetime.now(UTC), reason=LEGACY_REPAIR_REASON)
                _append_policy_event(audit, company_id=company_id, actor_id=administrator_id, action=AuditAction.AUTHORIZATION_POLICY_REVOKED.value, policy=revoked, details={"reason_code": "legacy_bootstrap_scope_replaced", "previous_scope_type": "company", "new_scope_type": PolicyScopeType.ANY.value})
                summary.legacy_revoked += 1
            create_values = expected | {"created_by_administrator_id": administrator_id, "valid_from": datetime.now(UTC)}
            for field in ("revoked_at", "revoked_by_administrator_id", "revocation_reason"):
                create_values.pop(field)
            policy = policies.create_policy(**create_values)
            _append_policy_event(audit, company_id=company_id, actor_id=administrator_id, action=AuditAction.AUTHORIZATION_POLICY_CREATED.value, policy=policy, details={"source_type": "bootstrap", "effect": definition.effect, "action_type": definition.action_type, "scope_type": PolicyScopeType.ANY.value})
            summary.verified += 1
            summary.created += 1
            if active: summary.legacy_replaced += 1
        session.commit()
        return summary
    except BaseException:
        session.rollback()
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create exact authorization safety defaults or explicitly repair their legacy scope.")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--company-id", type=UUID)
    scope.add_argument("--platform-defaults", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--administrator-id", required=True, type=UUID)
    parser.add_argument("--repair-legacy-scope", action="store_true", help="Replace only the exact legacy bootstrap scope shape.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.confirm:
        raise SystemExit("Refusing bootstrap or repair without --confirm; no policies were changed.")
    with SessionFactory() as session:
        administrator = AdministratorRepository(session).get_by_id(args.administrator_id)
        if administrator is None or not administrator.is_active or not administrator.is_superuser:
            raise SystemExit("An active platform superuser is required; no policies were changed.")
        if args.company_id is not None and CompanyRepository(session).get_by_id(args.company_id) is None:
            raise SystemExit("Company was not found; no policies were changed.")
        summary = run_bootstrap(session=session, administrator_id=administrator.id, company_id=None if args.platform_defaults else args.company_id, platform_defaults=args.platform_defaults, repair_legacy_scope=args.repair_legacy_scope, policies=AuthorizationRepository(session), audit=AuditLogService(AuditLogRepository(session)))
    print(f"Definitions verified: {summary.verified}; new definitions created: {summary.created}; legacy definitions revoked: {summary.legacy_revoked}; legacy definitions replaced: {summary.legacy_replaced}; no-op exact matches: {summary.exact_noops}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
