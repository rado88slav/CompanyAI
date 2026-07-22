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
