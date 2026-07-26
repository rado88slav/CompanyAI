"""Schemas for safe first-run setup detection."""

from pydantic import BaseModel
from pydantic import ConfigDict, Field, field_validator

from app.schemas.authentication import normalize_email
from app.schemas.company import CompanyCreate


class FirstRunStatusResponse(BaseModel):
    """Public first-run initialization status."""

    initialized: bool
    setup_required: bool
    administrator_count: int
    company_count: int
    bootstrap_method: str


class FirstRunInitializeRequest(BaseModel):
    """Input for single-use first-run initialization."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    company_name: str = Field(min_length=2, max_length=200)
    company_slug: str = Field(min_length=2, max_length=100)
    administrator_email: str = Field(min_length=3, max_length=320)
    administrator_full_name: str = Field(min_length=2, max_length=200)
    administrator_password: str = Field(min_length=14, max_length=128)
    language: str = Field(default="en", pattern="^(en|bg|de|fr)$")
    timezone: str = Field(default="UTC", min_length=1, max_length=80)

    @field_validator("company_slug")
    @classmethod
    def validate_company_slug(cls, value: str) -> str:
        return CompanyCreate(name="Validation Company", slug=value).slug

    @field_validator("administrator_email")
    @classmethod
    def validate_administrator_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("administrator_full_name")
    @classmethod
    def validate_administrator_full_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Administrator name must contain at least two characters.")
        return normalized

    @field_validator("administrator_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if (
            not any(char.islower() for char in value)
            or not any(char.isupper() for char in value)
            or not any(char.isdigit() for char in value)
            or not any(not char.isalnum() for char in value)
        ):
            raise ValueError(
                "Password must include lowercase, uppercase, digit and symbol characters."
            )
        return value


class FirstRunInitializeResponse(BaseModel):
    """Safe response after first-run initialization."""

    initialized: bool
    company_id: str
    company_slug: str
    administrator_id: str
    administrator_email: str
