"""Company-scoped provider connections and encrypted credential history."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, LargeBinary, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProviderConnectionStatus(StrEnum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    REVOKED = "revoked"


class ProviderCredentialStatus(StrEnum):
    ACTIVE = "active"
    ROTATED = "rotated"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ProviderConnection(Base):
    __tablename__ = "provider_connections"
    __table_args__ = (
        UniqueConstraint("company_id", "slug", name="uq_provider_connections_company_slug"),
        UniqueConstraint("company_id", "id", name="uq_provider_connections_company_id"),
        CheckConstraint("provider_key ~ '^[a-z][a-z0-9_]*$'", name="ck_provider_connections_key"),
        CheckConstraint("status IN ('inactive','active','revoked')", name="ck_provider_connections_status"),
        CheckConstraint("jsonb_typeof(configuration)='object'", name="ck_provider_connections_config_object"),
        CheckConstraint("jsonb_typeof(metadata)='object'", name="ck_provider_connections_metadata_object"),
        CheckConstraint("(status='active' AND activated_at IS NOT NULL AND activated_by_administrator_id IS NOT NULL) OR status<>'active'", name="ck_provider_connections_activation"),
        CheckConstraint("(status='revoked' AND revoked_at IS NOT NULL AND revoked_by_administrator_id IS NOT NULL) OR status<>'revoked'", name="ck_provider_connections_revocation"),
        CheckConstraint("(deactivated_at IS NULL) = (deactivated_by_administrator_id IS NULL)", name="ck_provider_connections_deactivation_actor"),
        Index("ix_provider_connections_company_status_provider", "company_id", "status", "provider_key"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    provider_key: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    authentication_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="inactive", server_default="inactive")
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    updated_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    activated_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    deactivated_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    revoked_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderCredential(Base):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        UniqueConstraint("company_id", "provider_connection_id", "id", name="uq_provider_credentials_identity"),
        ForeignKeyConstraint(["company_id", "provider_connection_id"], ["provider_connections.company_id", "provider_connections.id"], name="fk_provider_credentials_company_connection", ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "provider_connection_id", "rotated_from_credential_id"], ["provider_credentials.company_id", "provider_credentials.provider_connection_id", "provider_credentials.id"], name="fk_provider_credentials_rotation", ondelete="RESTRICT"),
        CheckConstraint("status IN ('active','rotated','revoked','expired')", name="ck_provider_credentials_status"),
        CheckConstraint("(status='revoked' AND revoked_at IS NOT NULL AND revoked_by_administrator_id IS NOT NULL) OR status<>'revoked'", name="ck_provider_credentials_revocation"),
        CheckConstraint("octet_length(nonce)=12", name="ck_provider_credentials_nonce"),
        CheckConstraint("encryption_version > 0 AND credential_schema_version > 0", name="ck_provider_credentials_versions"),
        CheckConstraint("encryption_revision >= 0", name="ck_provider_credentials_encryption_revision"),
        CheckConstraint("encryption_key_id IS NULL OR encryption_key_id ~ '^[a-z][a-z0-9_-]{0,63}$'", name="ck_provider_credentials_encryption_key_id"),
        Index("uq_provider_credentials_active", "company_id", "provider_connection_id", unique=True, postgresql_where=text("status='active'")),
        Index("ix_provider_credentials_connection_created", "company_id", "provider_connection_id", "created_at"),
        Index("ix_provider_credentials_encryption_key_id_id", "encryption_key_id", "id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    provider_connection_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    encrypted_payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encryption_version: Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")
    encryption_key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    encryption_revision: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    credential_schema_version: Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")
    rotated_from_credential_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    revoked_by_administrator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("administrators.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"ProviderCredential(id={self.id!r}, status={self.status!r}, encrypted_payload=**********, nonce=**********)"
