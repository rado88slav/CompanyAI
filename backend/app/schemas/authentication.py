"""Pydantic schemas for administrator authentication."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

_EMAIL_PATTERN = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)


def normalize_email(value: str) -> str:
    """Normalize and validate an administrator email address."""

    normalized = value.strip().lower()

    if not _EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError(
            "A valid email address is required."
        )

    return normalized


class AdministratorCreate(BaseModel):
    """Internal input for creating an administrator."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(
        min_length=3,
        max_length=320,
        examples=["admin@example.com"],
    )

    full_name: str = Field(
        min_length=2,
        max_length=200,
        examples=["Local Administrator"],
    )

    password: str = Field(
        min_length=12,
        max_length=128,
    )

    is_superuser: bool = False

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Normalize the administrator email."""

        return normalize_email(value)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        """Normalize and validate the administrator name."""

        normalized = " ".join(value.split())

        if len(normalized) < 2:
            raise ValueError(
                "Administrator name must contain at least two characters."
            )

        return normalized


class LoginRequest(BaseModel):
    """Administrator login credentials."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(
        min_length=3,
        max_length=320,
    )

    password: str = Field(
        min_length=1,
        max_length=128,
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Normalize the login email."""

        return normalize_email(value)


class AdministratorResponse(BaseModel):
    """Public administrator account information."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """Successful access-token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
