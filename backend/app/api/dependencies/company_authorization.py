"""Central FastAPI authorization dependencies for company roles."""

from typing import Annotated, Callable

from fastapi import Depends, HTTPException, status

from app.api.dependencies.authentication import require_current_administrator
from app.api.dependencies.company_context import require_matching_active_company
from app.core.company_permissions import CompanyPermission, role_has_permission
from app.models.administrator import Administrator
from app.schemas.company_context import ActiveCompanyContext


def require_platform_superuser(administrator: Annotated[Administrator, Depends(require_current_administrator)]) -> Administrator:
    if not administrator.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform superuser access is required.")
    return administrator


def require_company_permission(permission: CompanyPermission) -> Callable[..., ActiveCompanyContext]:
    def dependency(context: Annotated[ActiveCompanyContext, Depends(require_matching_active_company)]) -> ActiveCompanyContext:
        if context.is_platform_superuser:
            return context
        if context.membership is None or not role_has_permission(context.membership.role, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient company permission.")
        return context
    return dependency


require_company_settings_read = require_company_permission(CompanyPermission.SETTINGS_READ)
require_company_settings_write = require_company_permission(CompanyPermission.SETTINGS_WRITE)
require_company_activity_read = require_company_permission(CompanyPermission.ACTIVITY_READ)
require_memberships_read = require_company_permission(CompanyPermission.MEMBERSHIPS_READ)
require_memberships_manage = require_company_permission(CompanyPermission.MEMBERSHIPS_MANAGE)
require_approvals_request = require_company_permission(CompanyPermission.APPROVALS_REQUEST)
require_approvals_read = require_company_permission(CompanyPermission.APPROVALS_READ)
require_approvals_decide = require_company_permission(CompanyPermission.APPROVALS_DECIDE)
require_authorization_policies_read = require_company_permission(CompanyPermission.AUTHORIZATION_POLICIES_READ)
require_authorization_policies_manage = require_company_permission(CompanyPermission.AUTHORIZATION_POLICIES_MANAGE)
require_authorization_usage_read = require_company_permission(CompanyPermission.AUTHORIZATION_USAGE_READ)
require_agents_read = require_company_permission(CompanyPermission.AGENTS_READ)
require_agents_manage = require_company_permission(CompanyPermission.AGENTS_MANAGE)
require_tools_read = require_company_permission(CompanyPermission.TOOLS_READ)
require_tools_manage = require_company_permission(CompanyPermission.TOOLS_MANAGE)
require_providers_read = require_company_permission(CompanyPermission.PROVIDERS_READ)
require_providers_manage = require_company_permission(CompanyPermission.PROVIDERS_MANAGE)
require_provider_executions_read = require_company_permission(CompanyPermission.PROVIDER_EXECUTIONS_READ)
require_provider_executions_manage = require_company_permission(CompanyPermission.PROVIDER_EXECUTIONS_MANAGE)
require_emails_read = require_company_permission(CompanyPermission.EMAILS_READ)
require_emails_write = require_company_permission(CompanyPermission.EMAILS_WRITE)
