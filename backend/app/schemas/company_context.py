"""Typed request and response schemas for active company context."""

from dataclasses import dataclass

from pydantic import BaseModel

from app.models.administrator import Administrator
from app.models.company import Company
from app.schemas.company import CompanyResponse


@dataclass(frozen=True, slots=True)
class ActiveCompanyContext:
    """Authenticated administrator and company resolved for one request."""

    administrator: Administrator
    company: Company


class ActiveCompanyContextResponse(BaseModel):
    """Public representation of the resolved active company context."""

    company: CompanyResponse
