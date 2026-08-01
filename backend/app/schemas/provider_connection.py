"""Public metadata-only schemas for Provider Connections."""

from datetime import datetime
import json
import re
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from app.core.provider_connections import ProviderDescriptor, provider_registry, validate_safe_object
from app.models.provider_connection import ProviderConnectionStatus, ProviderCredentialStatus
from app.services.generic_smtp_imap import GENERIC_MAILBOX_HEALTH_KEY

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
HOST_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,251}[A-Za-z0-9]$")
GENERIC_SMTP_IMAP_SECURITY_VALUES = {"ssl_tls", "starttls"}


def validate_generic_smtp_imap_configuration(value: dict[str, Any]) -> dict[str, Any]:
    required_strings = {
        "email_address",
        "username",
        "smtp_host",
        "smtp_security",
        "imap_host",
        "imap_security",
        "imap_folder",
    }
    for key in required_strings:
        item = value.get(key)
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Generic SMTP/IMAP configuration is incomplete.")
        value[key] = item.strip()
    for key in ("sender_display_name", "reply_to_address"):
        item = value.get(key)
        if item is not None:
            if not isinstance(item, str):
                raise ValueError("Generic SMTP/IMAP configuration is invalid.")
            value[key] = item.strip()
    for key in ("email_address", "reply_to_address"):
        item = value.get(key)
        if item and not EMAIL_PATTERN.fullmatch(item):
            raise ValueError("Generic SMTP/IMAP email address is invalid.")
    for key in ("smtp_host", "imap_host"):
        item = value[key]
        if not HOST_PATTERN.fullmatch(item) or ".." in item:
            raise ValueError("Generic SMTP/IMAP host is invalid.")
        value[key] = item.casefold()
    for key in ("smtp_port", "imap_port"):
        item = value.get(key)
        if not isinstance(item, int) or item < 1 or item > 65535:
            raise ValueError("Generic SMTP/IMAP port is invalid.")
    for key in ("smtp_security", "imap_security"):
        if value[key] not in GENERIC_SMTP_IMAP_SECURITY_VALUES:
            raise ValueError("Generic SMTP/IMAP security mode is invalid.")
    return value


class ProviderDescriptorResponse(BaseModel):
    key: str
    display_name: str
    category: str
    authentication_type: str
    required_secret_fields: list[str]
    optional_secret_fields: list[str]
    configuration_fields: list[str]
    capabilities: list[str]
    credentials_may_expire: bool

    @classmethod
    def from_descriptor(cls, item: ProviderDescriptor) -> "ProviderDescriptorResponse":
        return cls(
            key=item.key, display_name=item.display_name, category=item.category,
            authentication_type=item.authentication_type,
            required_secret_fields=sorted(item.required_secret_fields),
            optional_secret_fields=sorted(item.optional_secret_fields),
            configuration_fields=sorted(item.configuration_fields),
            capabilities=sorted(item.capabilities),
            credentials_may_expire=item.credentials_may_expire,
        )


class ProviderConnectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    provider_key: str
    display_name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100)
    configuration: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_provider_fields(self) -> "ProviderConnectionCreate":
        descriptor = provider_registry.require(self.provider_key)
        if not SLUG_PATTERN.fullmatch(self.slug):
            raise ValueError("Connection slug is invalid.")
        self.configuration = validate_safe_object(self.configuration, allowed_fields=descriptor.configuration_fields, path="configuration")
        if descriptor.key == "generic_smtp_imap":
            self.configuration = validate_generic_smtp_imap_configuration(self.configuration)
            if GENERIC_MAILBOX_HEALTH_KEY in self.metadata:
                raise ValueError("Generic SMTP/IMAP health metadata is managed by the backend.")
        self.metadata = validate_safe_object(self.metadata, path="metadata")
        return self


class ProviderConnectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=100)
    configuration: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def require_change(self) -> "ProviderConnectionUpdate":
        data = self.model_dump(exclude_unset=True)
        if not data or any(value is None for value in data.values()):
            raise ValueError("At least one non-null field is required.")
        if self.slug is not None and not SLUG_PATTERN.fullmatch(self.slug):
            raise ValueError("Connection slug is invalid.")
        return self


class ProviderCredentialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    secrets: dict[str, SecretStr]
    expires_at: datetime | None = None

    def __repr__(self) -> str:
        return "ProviderCredentialCreate(secrets=**********, expires_at=%r)" % self.expires_at

    def validated_secrets(self, descriptor: ProviderDescriptor) -> dict[str, Any]:
        names = set(self.secrets)
        allowed = descriptor.required_secret_fields | descriptor.optional_secret_fields
        if not descriptor.required_secret_fields <= names or not names <= allowed:
            raise ValueError("Credential secret fields do not match the provider descriptor.")
        result: dict[str, Any] = {}
        for name, secret in self.secrets.items():
            value = secret.get_secret_value()
            if not value:
                raise ValueError("Credential secret values must be non-empty.")
            if name == "service_account_json":
                try:
                    structured = json.loads(value)
                except json.JSONDecodeError as exc:
                    raise ValueError("Structured credential value is invalid.") from exc
                if not isinstance(structured, dict):
                    raise ValueError("Structured credential value is invalid.")
                result[name] = structured
            else:
                result[name] = value
        if self.expires_at is not None and not descriptor.credentials_may_expire:
            raise ValueError("This provider does not support credential expiration.")
        return result


class ProviderConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    provider_key: str
    display_name: str
    slug: str
    authentication_type: str
    status: ProviderConnectionStatus
    configuration: dict[str, Any]
    metadata: dict[str, Any] = Field(validation_alias="metadata_")
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None
    deactivated_at: datetime | None
    revoked_at: datetime | None


class ProviderConnectionListResponse(BaseModel):
    items: list[ProviderConnectionResponse]
    total: int
    limit: int
    offset: int


class ProviderCredentialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    provider_connection_id: UUID
    status: ProviderCredentialStatus
    encryption_version: int
    credential_schema_version: int
    rotated_from_credential_id: UUID | None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None


class ProviderCredentialListResponse(BaseModel):
    items: list[ProviderCredentialResponse]
    total: int
    limit: int
    offset: int


class ProviderConnectionTestResponse(BaseModel):
    protocol: str
    status: str
    tested_at: datetime
    category: str
    message: str
    connection: ProviderConnectionResponse
