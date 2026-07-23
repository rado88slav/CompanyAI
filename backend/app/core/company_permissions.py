"""Central company role and permission definitions."""

from enum import StrEnum

from app.models.company_membership import CompanyRole


class CompanyPermission(StrEnum):
    SETTINGS_READ = "settings.read"
    SETTINGS_WRITE = "settings.write"
    ACTIVITY_READ = "activity.read"
    MEMBERSHIPS_READ = "memberships.read"
    MEMBERSHIPS_MANAGE = "memberships.manage"
    APPROVALS_REQUEST = "approvals.request"
    APPROVALS_READ = "approvals.read"
    APPROVALS_DECIDE = "approvals.decide"
    AUTHORIZATION_POLICIES_READ = "authorization_policies.read"
    AUTHORIZATION_POLICIES_MANAGE = "authorization_policies.manage"
    AUTHORIZATION_USAGE_READ = "authorization_usage.read"
    AGENTS_READ = "agents.read"
    AGENTS_MANAGE = "agents.manage"
    TOOLS_READ = "tools.read"
    TOOLS_MANAGE = "tools.manage"
    PROVIDERS_READ = "providers.read"
    PROVIDERS_MANAGE = "providers.manage"


ROLE_PERMISSIONS: dict[str, frozenset[CompanyPermission]] = {
    CompanyRole.OWNER.value: frozenset(CompanyPermission),
    CompanyRole.ADMIN.value: frozenset({CompanyPermission.SETTINGS_READ, CompanyPermission.SETTINGS_WRITE, CompanyPermission.ACTIVITY_READ, CompanyPermission.MEMBERSHIPS_READ, CompanyPermission.MEMBERSHIPS_MANAGE, CompanyPermission.APPROVALS_REQUEST, CompanyPermission.APPROVALS_READ, CompanyPermission.APPROVALS_DECIDE, CompanyPermission.AUTHORIZATION_POLICIES_READ, CompanyPermission.AUTHORIZATION_POLICIES_MANAGE, CompanyPermission.AUTHORIZATION_USAGE_READ, CompanyPermission.AGENTS_READ, CompanyPermission.AGENTS_MANAGE, CompanyPermission.TOOLS_READ, CompanyPermission.TOOLS_MANAGE, CompanyPermission.PROVIDERS_READ, CompanyPermission.PROVIDERS_MANAGE}),
    CompanyRole.OPERATOR.value: frozenset({CompanyPermission.SETTINGS_READ, CompanyPermission.ACTIVITY_READ, CompanyPermission.APPROVALS_REQUEST, CompanyPermission.APPROVALS_READ, CompanyPermission.AGENTS_READ, CompanyPermission.TOOLS_READ, CompanyPermission.PROVIDERS_READ}),
    CompanyRole.VIEWER.value: frozenset({CompanyPermission.SETTINGS_READ, CompanyPermission.ACTIVITY_READ, CompanyPermission.AGENTS_READ, CompanyPermission.TOOLS_READ, CompanyPermission.PROVIDERS_READ}),
}


def role_has_permission(role: str, permission: CompanyPermission) -> bool:
    """Return whether a normalized role grants one permission."""

    return permission in ROLE_PERMISSIONS.get(role, frozenset())
