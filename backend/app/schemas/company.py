"""Pydantic schemas for the Company domain."""

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
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
        """Normalize and validate a company name."""

        normalized = " ".join(value.split())

        if len(normalized) < 2:
            raise ValueError(
                "Company name must contain at least two characters."
            )

        return normalized

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        """Normalize a valid company slug to lowercase."""

        return value.lower()


class CompanyUpdate(BaseModel):
    """Input data for partially updating a company."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=200,
        examples=["Updated Heating Systems"],
    )

    slug: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        examples=["updated-heating-systems"],
    )

    @field_validator("name")
    @classmethod
    def validate_name(
        cls,
        value: str | None,
    ) -> str | None:
        """Normalize and validate an optional company name."""

        if value is None:
            return None

        normalized = " ".join(value.split())

        if len(normalized) < 2:
            raise ValueError(
                "Company name must contain at least two characters."
            )

        return normalized

    @field_validator("slug")
    @classmethod
    def normalize_slug(
        cls,
        value: str | None,
    ) -> str | None:
        """Normalize an optional valid company slug."""

        if value is None:
            return None

        return value.lower()

    @model_validator(mode="after")
    def validate_update_payload(self) -> Self:
        """Require at least one non-null field."""

        update_fields = self.model_dump(
            exclude_unset=True,
        )

        if not update_fields:
            raise ValueError(
                "At least one company field must be provided."
            )

        if any(
            value is None
            for value in update_fields.values()
        ):
            raise ValueError(
                "Company update fields cannot be null."
            )

        return self


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
