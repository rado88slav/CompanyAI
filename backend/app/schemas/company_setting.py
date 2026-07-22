"""Pydantic schemas for company-owned settings."""

from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
)


class CompanySettingUpsert(BaseModel):
    """Input value for creating or replacing a company setting."""

    model_config = ConfigDict(
        extra="forbid",
    )

    value: JsonValue = Field(
        examples=[
            {
                "timezone": "Europe/Sofia",
            }
        ],
    )


class CompanySettingResponse(BaseModel):
    """Public company setting response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    category: str
    key: str
    value: JsonValue
    created_at: datetime
    updated_at: datetime


class CompanySettingListResponse(BaseModel):
    """Paginated company setting collection."""

    items: list[CompanySettingResponse]
    total: int
    limit: int
    offset: int
