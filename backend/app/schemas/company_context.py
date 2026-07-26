"""Typed request and response schemas for active company context."""

from dataclasses import dataclass

from pydantic import BaseModel

from app.models.administrator import Administrator
from app.models.company import Company
from app.models.company_membership import CompanyMembership
from app.schemas.company import CompanyResponse
from app.models.company_membership import CompanyRole


@dataclass(frozen=True, slots=True)
class ActiveCompanyContext:
    """Authenticated administrator and company resolved for one request."""

    administrator: Administrator
    company: Company
    membership: CompanyMembership | None
    is_platform_superuser: bool


class ActiveCompanyContextResponse(BaseModel):
    """Public representation of the resolved active company context."""

    company: CompanyResponse
    membership_role: CompanyRole | None
    is_platform_superuser: bool


class AvailableCompanyContext(BaseModel):
    """A company the authenticated administrator may select."""

    company: CompanyResponse
    membership_role: CompanyRole | None
    is_platform_superuser: bool


class AvailableCompanyContextListResponse(BaseModel):
    """Page of selectable active company contexts."""

    items: list[AvailableCompanyContext]
    total: int
    limit: int
    offset: int
