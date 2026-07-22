"""API schemas for company memberships."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.company_membership import CompanyRole


class CompanyMembershipCreate(BaseModel):
    administrator_id: UUID
    role: CompanyRole


class CompanyMembershipRoleUpdate(BaseModel):
    role: CompanyRole


class AdministratorSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    full_name: str
    is_active: bool


class CompanyMembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    administrator_id: UUID
    role: CompanyRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    administrator: AdministratorSummary


class CompanyMembershipListResponse(BaseModel):
    items: list[CompanyMembershipResponse]
    total: int
    limit: int
    offset: int


class CompanySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    slug: str
    status: str
    is_active: bool


class MyCompanyMembershipResponse(BaseModel):
    id: UUID
    role: CompanyRole
    company: CompanySummary


class MyCompanyMembershipListResponse(BaseModel):
    items: list[MyCompanyMembershipResponse]
    total: int
    limit: int
    offset: int
