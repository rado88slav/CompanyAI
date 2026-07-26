"""Atomic Provider Connections lifecycle and trusted credential resolution."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.credential_encryption import CredentialEncryptionService, DecryptedCredential
from app.core.provider_connections import provider_registry, validate_safe_object
from app.db.session import get_db_session
from app.models.administrator import Administrator
from app.models.audit_log import AuditAction
from app.models.provider_connection import ProviderConnection, ProviderCredential
from app.repositories.audit_log import AuditLogRepository
from app.repositories.provider_connection import ProviderConnectionRepository
from app.schemas.provider_connection import ProviderConnectionCreate, ProviderConnectionUpdate, ProviderCredentialCreate
from app.services.audit_log import AuditLogService


class ProviderNotFoundError(Exception): pass
class ProviderConflictError(Exception): pass
class ProviderLifecycleError(Exception): pass
class ProviderCredentialError(Exception): pass


@dataclass(slots=True)
class ResolvedProviderCredential:
    connection: ProviderConnection
    credential: ProviderCredential
    secret_bundle: DecryptedCredential

    def __repr__(self) -> str:
        return f"ResolvedProviderCredential(connection_id={self.connection.id!r}, credential_id={self.credential.id!r}, secret_bundle=**********)"


class ProviderConnectionService:
    def __init__(self, repository: ProviderConnectionRepository, audit: AuditLogService, session: Session, encryption: CredentialEncryptionService) -> None:
        self._repository, self._audit, self._session, self._encryption = repository, audit, session, encryption

    def _connection(self, company_id: UUID, connection_id: UUID, *, lock: bool = False) -> ProviderConnection:
        item = self._repository.connection(company_id=company_id, connection_id=connection_id, for_update=lock)
        if item is None: raise ProviderNotFoundError
        return item

    def _audit_event(self, *, company_id: UUID, actor: Administrator, action: AuditAction, resource_id: UUID, details: dict[str, object]) -> None:
        self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=action.value, resource_type="provider_connection" if action.value.startswith("provider_connection.") else "provider_credential", resource_id=resource_id, details=details)

    def create_connection(self, *, company_id: UUID, data: ProviderConnectionCreate, actor: Administrator) -> ProviderConnection:
        descriptor = provider_registry.require(data.provider_key)
        try:
            item = self._repository.create_connection(company_id=company_id, provider_key=descriptor.key, display_name=data.display_name, slug=data.slug, authentication_type=descriptor.authentication_type, status="inactive", configuration=data.configuration, metadata_=data.metadata, created_by_administrator_id=actor.id)
            self._audit_event(company_id=company_id, actor=actor, action=AuditAction.PROVIDER_CONNECTION_CREATED, resource_id=item.id, details={"connection_id": str(item.id), "provider_key": item.provider_key, "status": item.status})
            self._session.commit(); return item
        except IntegrityError as exc:
            self._session.rollback(); raise ProviderConflictError from exc
        except Exception:
            self._session.rollback(); raise

    def setup_local_test_email_connection(self, *, company_id: UUID, actor: Administrator, app_environment: str) -> ProviderConnection:
        if app_environment not in {"development", "test"}:
            raise ProviderLifecycleError
        descriptor = provider_registry.require("local_test_email")
        item = self._repository.connection_by_slug(company_id=company_id, slug="local-test-email", for_update=True)
        if item is not None:
            if (
                item.provider_key != descriptor.key
                or item.authentication_type != descriptor.authentication_type
                or item.status == "revoked"
                or item.configuration
            ):
                raise ProviderConflictError
            changed = False
            if item.display_name != "Local Test Email Provider":
                item.display_name = "Local Test Email Provider"
                item.updated_by_administrator_id = actor.id
                changed = True
            if item.status != "active":
                item.status = "active"
                item.activated_at = datetime.now(UTC)
                item.activated_by_administrator_id = actor.id
                item.deactivated_at = item.deactivated_by_administrator_id = None
                changed = True
            if changed:
                self._repository.save_connection(item)
                self._audit_event(company_id=company_id, actor=actor, action=AuditAction.PROVIDER_CONNECTION_ACTIVATED, resource_id=item.id, details={"connection_id": str(item.id), "provider_key": item.provider_key, "status": item.status, "development_only": True})
                self._session.commit()
            return item
        try:
            item = self._repository.create_connection(
                company_id=company_id,
                provider_key=descriptor.key,
                display_name="Local Test Email Provider",
                slug="local-test-email",
                authentication_type=descriptor.authentication_type,
                status="active",
                configuration={},
                metadata_={"development_only": True, "live_delivery": False},
                created_by_administrator_id=actor.id,
                activated_by_administrator_id=actor.id,
                activated_at=datetime.now(UTC),
            )
            self._audit_event(company_id=company_id, actor=actor, action=AuditAction.PROVIDER_CONNECTION_CREATED, resource_id=item.id, details={"connection_id": str(item.id), "provider_key": item.provider_key, "status": item.status, "development_only": True, "live_delivery": False})
            self._session.commit()
            return item
        except IntegrityError as exc:
            self._session.rollback()
            raise ProviderConflictError from exc
        except Exception:
            self._session.rollback()
            raise

    def list_connections(self, *, company_id: UUID, limit: int, offset: int) -> tuple[list[ProviderConnection], int]:
        return self._repository.list_connections(company_id=company_id, limit=limit, offset=offset), self._repository.count_connections(company_id=company_id)

    def get_connection(self, *, company_id: UUID, connection_id: UUID) -> ProviderConnection:
        return self._connection(company_id, connection_id)

    def update_connection(self, *, company_id: UUID, connection_id: UUID, data: ProviderConnectionUpdate, actor: Administrator) -> ProviderConnection:
        item = self._connection(company_id, connection_id, lock=True)
        if item.status == "revoked": raise ProviderLifecycleError
        changes = data.model_dump(exclude_unset=True)
        if "configuration" in changes:
            changes["configuration"] = validate_safe_object(changes["configuration"], allowed_fields=provider_registry.require(item.provider_key).configuration_fields, path="configuration")
        if "metadata" in changes:
            changes["metadata_"] = validate_safe_object(changes.pop("metadata"), path="metadata")
        for field, value in changes.items(): setattr(item, field, value)
        item.updated_by_administrator_id = actor.id
        try:
            self._repository.save_connection(item)
            self._audit_event(company_id=company_id, actor=actor, action=AuditAction.PROVIDER_CONNECTION_UPDATED, resource_id=item.id, details={"connection_id": str(item.id), "provider_key": item.provider_key, "changed_fields": sorted(field.removesuffix("_") for field in changes)})
            self._session.commit(); return item
        except IntegrityError as exc:
            self._session.rollback(); raise ProviderConflictError from exc
        except Exception:
            self._session.rollback(); raise

    def set_status(self, *, company_id: UUID, connection_id: UUID, target: str, actor: Administrator) -> ProviderConnection:
        item = self._connection(company_id, connection_id, lock=True)
        if item.status == "revoked": raise ProviderLifecycleError
        now = datetime.now(UTC)
        action = {"active": AuditAction.PROVIDER_CONNECTION_ACTIVATED, "inactive": AuditAction.PROVIDER_CONNECTION_DEACTIVATED, "revoked": AuditAction.PROVIDER_CONNECTION_REVOKED}[target]
        if target == "active":
            credential = self._repository.active_credential(company_id=company_id, connection_id=connection_id, for_update=True)
            descriptor = provider_registry.require(item.provider_key)
            if descriptor.required_secret_fields and (credential is None or (credential.expires_at is not None and credential.expires_at <= now)): raise ProviderLifecycleError
            item.status, item.activated_at, item.activated_by_administrator_id = target, now, actor.id
            item.deactivated_at = item.deactivated_by_administrator_id = None
        elif target == "inactive":
            item.status, item.deactivated_at, item.deactivated_by_administrator_id = target, now, actor.id
        else:
            active = self._repository.active_credential(company_id=company_id, connection_id=connection_id, for_update=True)
            if active is not None:
                active.status, active.revoked_at, active.revoked_by_administrator_id = "revoked", now, actor.id
                self._repository.save_credential(active)
            item.status, item.revoked_at, item.revoked_by_administrator_id = target, now, actor.id
        try:
            self._repository.save_connection(item)
            self._audit_event(company_id=company_id, actor=actor, action=action, resource_id=item.id, details={"connection_id": str(item.id), "provider_key": item.provider_key, "status": target})
            self._session.commit(); return item
        except Exception:
            self._session.rollback(); raise

    def list_credentials(self, *, company_id: UUID, connection_id: UUID, limit: int, offset: int) -> tuple[list[ProviderCredential], int]:
        self._connection(company_id, connection_id)
        return self._repository.list_credentials(company_id=company_id, connection_id=connection_id, limit=limit, offset=offset), self._repository.count_credentials(company_id=company_id, connection_id=connection_id)

    def _new_credential(self, *, item: ProviderConnection, data: ProviderCredentialCreate, actor: Administrator, rotated_from: UUID | None) -> ProviderCredential:
        descriptor = provider_registry.require(item.provider_key)
        secrets = data.validated_secrets(descriptor)
        credential_id = uuid4()
        encrypted = self._encryption.encrypt(
            secrets,
            company_id=item.company_id,
            connection_id=item.id,
            credential_id=credential_id,
            provider_key=item.provider_key,
        )
        return self._repository.create_credential(id=credential_id, company_id=item.company_id, provider_connection_id=item.id, status="active", encrypted_payload=encrypted.ciphertext, nonce=encrypted.nonce, encryption_version=encrypted.encryption_version, encryption_key_id=encrypted.encryption_key_id, encryption_revision=encrypted.encryption_revision, credential_schema_version=1, rotated_from_credential_id=rotated_from, created_by_administrator_id=actor.id, expires_at=data.expires_at)

    def create_credential(self, *, company_id: UUID, connection_id: UUID, data: ProviderCredentialCreate, actor: Administrator) -> ProviderCredential:
        item = self._connection(company_id, connection_id, lock=True)
        if item.status == "revoked" or self._repository.active_credential(company_id=company_id, connection_id=connection_id, for_update=True): raise ProviderLifecycleError
        try:
            credential = self._new_credential(item=item, data=data, actor=actor, rotated_from=None)
            self._audit_event(company_id=company_id, actor=actor, action=AuditAction.PROVIDER_CREDENTIAL_CREATED, resource_id=credential.id, details={"connection_id": str(item.id), "provider_key": item.provider_key, "credential_id": str(credential.id), "expiration_present": credential.expires_at is not None, "encryption_version": credential.encryption_version, "encryption_key_id": credential.encryption_key_id, "encryption_revision": credential.encryption_revision})
            self._session.commit(); return credential
        except IntegrityError as exc:
            self._session.rollback(); raise ProviderConflictError from exc
        except Exception:
            self._session.rollback(); raise

    def rotate_credential(self, *, company_id: UUID, connection_id: UUID, credential_id: UUID, data: ProviderCredentialCreate, actor: Administrator) -> ProviderCredential:
        item = self._connection(company_id, connection_id, lock=True)
        old = self._repository.credential(company_id=company_id, connection_id=connection_id, credential_id=credential_id, for_update=True)
        if item.status == "revoked" or old is None or old.status != "active": raise ProviderLifecycleError
        old.status = "rotated"
        try:
            self._repository.save_credential(old)
            new = self._new_credential(item=item, data=data, actor=actor, rotated_from=old.id)
            self._audit_event(company_id=company_id, actor=actor, action=AuditAction.PROVIDER_CREDENTIAL_ROTATED, resource_id=new.id, details={"connection_id": str(item.id), "provider_key": item.provider_key, "credential_id": str(new.id), "previous_credential_id": str(old.id), "expiration_present": new.expires_at is not None, "encryption_version": new.encryption_version, "encryption_key_id": new.encryption_key_id, "encryption_revision": new.encryption_revision})
            self._session.commit(); return new
        except Exception:
            self._session.rollback(); raise

    def revoke_credential(self, *, company_id: UUID, connection_id: UUID, credential_id: UUID, actor: Administrator) -> ProviderCredential:
        item = self._connection(company_id, connection_id, lock=True)
        credential = self._repository.credential(company_id=company_id, connection_id=connection_id, credential_id=credential_id, for_update=True)
        if credential is None: raise ProviderNotFoundError
        if credential.status != "active": raise ProviderLifecycleError
        credential.status, credential.revoked_at, credential.revoked_by_administrator_id = "revoked", datetime.now(UTC), actor.id
        try:
            self._repository.save_credential(credential)
            if item.status == "active":
                item.status, item.deactivated_at, item.deactivated_by_administrator_id = "inactive", datetime.now(UTC), actor.id
                self._repository.save_connection(item)
            self._audit_event(company_id=company_id, actor=actor, action=AuditAction.PROVIDER_CREDENTIAL_REVOKED, resource_id=credential.id, details={"connection_id": str(item.id), "provider_key": item.provider_key, "credential_id": str(credential.id)})
            self._session.commit(); return credential
        except Exception:
            self._session.rollback(); raise

    def resolve(self, *, company_id: UUID, connection_id: UUID, provider_key: str) -> ResolvedProviderCredential:
        item = self._connection(company_id, connection_id)
        company = self._repository.company(company_id)
        credential = self._repository.active_credential(company_id=company_id, connection_id=connection_id)
        now = datetime.now(UTC)
        if company is None or not company.is_active or company.status != "active" or item.provider_key != provider_key or provider_registry.get(provider_key) is None or item.status != "active" or credential is None or credential.status != "active" or (credential.expires_at is not None and credential.expires_at <= now):
            raise ProviderCredentialError
        return ResolvedProviderCredential(
            item,
            credential,
            self._encryption.decrypt(
                credential.encrypted_payload,
                credential.nonce,
                company_id=company_id,
                connection_id=connection_id,
                credential_id=credential.id,
                provider_key=provider_key,
                encryption_version=credential.encryption_version,
                encryption_key_id=credential.encryption_key_id,
            ),
        )


def get_provider_connection_service(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> ProviderConnectionService:
    keyring = request.app.state.credential_encryption_keyring
    return ProviderConnectionService(ProviderConnectionRepository(session), AuditLogService(AuditLogRepository(session)), session, CredentialEncryptionService(keyring))
