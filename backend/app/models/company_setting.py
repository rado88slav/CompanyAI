"""Company-owned setting database model."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CompanySetting(Base):
    """A non-secret configuration value owned by one company."""

    __tablename__ = "company_settings"
    __table_args__ = (
        CheckConstraint(
            "length(category) > 0",
            name="ck_company_settings_category_not_empty",
        ),
        CheckConstraint(
            "length(key) > 0",
            name="ck_company_settings_key_not_empty",
        ),
        UniqueConstraint(
            "company_id",
            "category",
            "key",
            name="uq_company_settings_company_category_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "companies.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    value: Mapped[Any] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
