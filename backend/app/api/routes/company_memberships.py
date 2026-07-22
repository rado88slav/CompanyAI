"""HTTP endpoints for company memberships and roles."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.authentication import require_current_administrator
from app.api.dependencies.company_authorization import require_memberships_manage, require_memberships_read
from app.models.administrator import Administrator
from app.models.company_membership import CompanyRole
from app.schemas.company_context import ActiveCompanyContext
from app.schemas.company_membership import CompanyMembershipCreate, CompanyMembershipListResponse, CompanyMembershipResponse, CompanyMembershipRoleUpdate, MyCompanyMembershipListResponse, MyCompanyMembershipResponse
from app.services.company import CompanyNotFoundError
from app.services.company_membership import CompanyMembershipService, InactiveAdministratorError, LastActiveOwnerError, MembershipAuthorizationError, MembershipConflictError, MembershipNotFoundError, get_company_membership_service

router = APIRouter(tags=["company-memberships"])


def _raise_membership_error(exc: Exception) -> None:
    if isinstance(exc, (CompanyNotFoundError, MembershipNotFoundError)):
        raise HTTPException(status_code=404, detail="Company membership or related resource was not found.") from exc
    if isinstance(exc, MembershipAuthorizationError):
        raise HTTPException(status_code=403, detail="Membership operation is forbidden.") from exc
    if isinstance(exc, InactiveAdministratorError):
        raise HTTPException(status_code=409, detail="Inactive administrator cannot have an active membership.") from exc
    if isinstance(exc, LastActiveOwnerError):
        raise HTTPException(status_code=409, detail="The last active owner cannot be changed or deactivated.") from exc
    if isinstance(exc, MembershipConflictError):
        raise HTTPException(status_code=409, detail="A membership already exists for this administrator and company.") from exc
    raise exc


@router.post("/companies/{company_id}/memberships", response_model=CompanyMembershipResponse, status_code=status.HTTP_201_CREATED)
def create_membership(company_id: UUID, data: CompanyMembershipCreate, context: Annotated[ActiveCompanyContext, Depends(require_memberships_manage)], service: Annotated[CompanyMembershipService, Depends(get_company_membership_service)]) -> CompanyMembershipResponse:
    try:
        membership = service.create_membership(company_id=company_id, administrator_id=data.administrator_id, role=data.role.value, actor=context.administrator, actor_membership=context.membership)
    except (CompanyNotFoundError, MembershipNotFoundError, MembershipAuthorizationError, InactiveAdministratorError, MembershipConflictError) as exc:
        _raise_membership_error(exc)
    return CompanyMembershipResponse.model_validate(membership)


@router.get("/companies/{company_id}/memberships", response_model=CompanyMembershipListResponse)
def list_memberships(company_id: UUID, _context: Annotated[ActiveCompanyContext, Depends(require_memberships_read)], service: Annotated[CompanyMembershipService, Depends(get_company_membership_service)], role: CompanyRole | None = None, is_active: bool | None = None, limit: Annotated[int, Query(ge=1, le=100)] = 50, offset: Annotated[int, Query(ge=0)] = 0) -> CompanyMembershipListResponse:
    items, total = service.list_memberships(company_id=company_id, role=role.value if role else None, is_active=is_active, limit=limit, offset=offset)
    return CompanyMembershipListResponse(items=[CompanyMembershipResponse.model_validate(item) for item in items], total=total, limit=limit, offset=offset)


@router.get("/companies/{company_id}/memberships/{membership_id}", response_model=CompanyMembershipResponse)
def get_membership(company_id: UUID, membership_id: UUID, _context: Annotated[ActiveCompanyContext, Depends(require_memberships_read)], service: Annotated[CompanyMembershipService, Depends(get_company_membership_service)]) -> CompanyMembershipResponse:
    try:
        membership = service.get_membership(company_id=company_id, membership_id=membership_id)
    except MembershipNotFoundError as exc:
        _raise_membership_error(exc)
    return CompanyMembershipResponse.model_validate(membership)


@router.patch("/companies/{company_id}/memberships/{membership_id}/role", response_model=CompanyMembershipResponse)
def change_membership_role(company_id: UUID, membership_id: UUID, data: CompanyMembershipRoleUpdate, context: Annotated[ActiveCompanyContext, Depends(require_memberships_manage)], service: Annotated[CompanyMembershipService, Depends(get_company_membership_service)]) -> CompanyMembershipResponse:
    try:
        membership = service.change_role(company_id=company_id, membership_id=membership_id, role=data.role.value, actor=context.administrator, actor_membership=context.membership)
    except (MembershipNotFoundError, MembershipAuthorizationError, LastActiveOwnerError) as exc:
        _raise_membership_error(exc)
    return CompanyMembershipResponse.model_validate(membership)


def _set_membership_active(*, company_id: UUID, membership_id: UUID, is_active: bool, context: ActiveCompanyContext, service: CompanyMembershipService) -> CompanyMembershipResponse:
    try:
        membership = service.set_active(company_id=company_id, membership_id=membership_id, is_active=is_active, actor=context.administrator, actor_membership=context.membership)
    except (MembershipNotFoundError, MembershipAuthorizationError, LastActiveOwnerError, InactiveAdministratorError) as exc:
        _raise_membership_error(exc)
    return CompanyMembershipResponse.model_validate(membership)


@router.post("/companies/{company_id}/memberships/{membership_id}/activate", response_model=CompanyMembershipResponse)
def activate_membership(company_id: UUID, membership_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_memberships_manage)], service: Annotated[CompanyMembershipService, Depends(get_company_membership_service)]) -> CompanyMembershipResponse:
    return _set_membership_active(company_id=company_id, membership_id=membership_id, is_active=True, context=context, service=service)


@router.post("/companies/{company_id}/memberships/{membership_id}/deactivate", response_model=CompanyMembershipResponse)
def deactivate_membership(company_id: UUID, membership_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_memberships_manage)], service: Annotated[CompanyMembershipService, Depends(get_company_membership_service)]) -> CompanyMembershipResponse:
    return _set_membership_active(company_id=company_id, membership_id=membership_id, is_active=False, context=context, service=service)


@router.get("/company-memberships/me", response_model=MyCompanyMembershipListResponse)
def list_my_memberships(administrator: Annotated[Administrator, Depends(require_current_administrator)], service: Annotated[CompanyMembershipService, Depends(get_company_membership_service)], limit: Annotated[int, Query(ge=1, le=100)] = 50, offset: Annotated[int, Query(ge=0)] = 0) -> MyCompanyMembershipListResponse:
    items, total = service.list_my_memberships(administrator_id=administrator.id, limit=limit, offset=offset)
    return MyCompanyMembershipListResponse(items=[MyCompanyMembershipResponse(id=item.id, role=CompanyRole(item.role), company=item.company) for item in items], total=total, limit=limit, offset=offset)
