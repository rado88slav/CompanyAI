"""Pydantic schemas for the Company domain."""

from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.models.company import CompanyStatus


class CompanyCreate(BaseModel):
    """Input data for creating a company."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    name: str = Field(
        min_length=2,
        max_length=200,
        examples=["Example Heating Systems"],
    )

    slug: str = Field(
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        examples=["example-heating-systems"],
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Reject names containing only whitespace."""

        normalized = " ".join(value.split())

        if len(normalized) < 2:
            raise ValueError(
                "Company name must contain at least two characters."
            )

        return normalized

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        """Normalize company slugs to lowercase."""

        return value.lower()


class CompanyResponse(BaseModel):
    """Public company response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    status: CompanyStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CompanyListResponse(BaseModel):
    """Paginated company collection response."""

    items: list[CompanyResponse]
    total: int
    limit: int
    offset: int
