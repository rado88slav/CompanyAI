"""Focused Provider Connections security and contract tests."""
import base64
import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import ValidationError

from app.core.company_permissions import CompanyPermission, role_has_permission
from app.core.credential_encryption import CURRENT_ENCRYPTION_VERSION, LEGACY_ENCRYPTION_KEY_ID, CredentialEncryptionError, CredentialEncryptionService, credential_aad, decode_encryption_key, parse_encryption_keyring
from app.core.provider_connections import ProviderDescriptor, ProviderRegistry, provider_registry, validate_safe_object
from app.main import app
from app.models.audit_log import AuditAction
from app.models.provider_connection import ProviderConnection, ProviderCredential
from app.schemas.provider_connection import ProviderConnectionCreate, ProviderCredentialCreate
from app.services.provider_connection import ProviderConnectionService, ProviderLifecycleError


def _encryption_service(
    encoded_key: str = "00" * 32,
    *,
    active_key_id: str = "legacy",
) -> CredentialEncryptionService:
    return CredentialEncryptionService(
        parse_encryption_keyring(
            json.dumps({active_key_id: encoded_key}),
            active_key_id=active_key_id,
        )
    )


def test_immutable_builtin_descriptors_include_local_test_email() -> None:
    assert {x.key for x in provider_registry.all()} == {"retell","twilio","telnyx","microsoft_365","google_workspace","lemlist","instantly","smartlead","local_test_email","local_mock_email"}
    assert provider_registry.require("local_test_email").required_secret_fields == frozenset()
    assert provider_registry.require("local_mock_email").required_secret_fields == frozenset()
    assert "email.campaign.read" in provider_registry.require("lemlist").capabilities
    with pytest.raises(AttributeError): provider_registry.require("retell").key = "changed"  # type: ignore[misc]


def test_registry_exact_duplicate_safe_and_not_executable() -> None:
    registry = ProviderRegistry()
    item = ProviderDescriptor("example","Example","test","api_key",frozenset({"api_key"}),frozenset(),frozenset(),frozenset({"test.run"}))
    registry.register(item)
    assert registry.get("example") is item and registry.get("Example") is None
    with pytest.raises(ValueError): registry.register(item)
    assert not {"import_path","module","callable","handler","command"}.intersection(ProviderDescriptor.__dataclass_fields__)


@pytest.mark.parametrize("field", ["password","Secret","api_key","AUTH_TOKEN","handler","import_path","module","source","shell","command","subprocess"])
def test_safe_objects_recursively_reject_sensitive_executable_keys(field: str) -> None:
    with pytest.raises(ValueError): validate_safe_object({"nested": {field: "x"}})


def test_safe_objects_are_allowlisted_and_reject_url_credentials() -> None:
    assert validate_safe_object({"region":"us1"}, allowed_fields=frozenset({"region"})) == {"region":"us1"}
    for value, allowed in (([],None),({"unknown":"x"},frozenset({"region"})),({"name":"x","NAME":"y"},None),({"callback_url":"https://user:pass@example.test"},None)):
        with pytest.raises(ValueError): validate_safe_object(value, allowed_fields=allowed)


def test_connection_schema_uses_trusted_provider() -> None:
    assert ProviderConnectionCreate(provider_key="twilio",display_name="Primary",slug="primary",configuration={"region":"us1"}).provider_key == "twilio"
    with pytest.raises(ValidationError): ProviderConnectionCreate(provider_key="unknown",display_name="Bad",slug="bad")
    with pytest.raises(ValidationError): ProviderConnectionCreate(provider_key="twilio",display_name="Bad",slug="bad",configuration={"api_key":"x"})


def test_secret_request_redaction_and_validation() -> None:
    raw = "SENSITIVE-VALUE"
    request = ProviderCredentialCreate(secrets={"api_key":raw})
    assert raw not in repr(request) and raw not in str(request)
    assert request.validated_secrets(provider_registry.require("retell"))["api_key"] == raw
    for payload in ({},{"unknown":"x"},{"api_key":""}):
        with pytest.raises(ValueError) as error: ProviderCredentialCreate(secrets=payload).validated_secrets(provider_registry.require("retell"))
        assert raw not in str(error.value)


def test_service_account_json_requires_object() -> None:
    request = ProviderCredentialCreate(secrets={"service_account_json":'{"type":"service_account"}'})
    assert request.validated_secrets(provider_registry.require("google_workspace"))["service_account_json"]["type"] == "service_account"
    with pytest.raises(ValueError): ProviderCredentialCreate(secrets={"service_account_json":"[]"}).validated_secrets(provider_registry.require("google_workspace"))


def test_aes_gcm_roundtrip_random_nonce_and_no_plaintext() -> None:
    service = _encryption_service()
    company, connection, credential = uuid4(), uuid4(), uuid4()
    secret = "plaintext-provider-secret"
    first = service.encrypt({"api_key":secret}, company_id=company, connection_id=connection, credential_id=credential, provider_key="retell")
    second = service.encrypt({"api_key":secret}, company_id=company, connection_id=connection, credential_id=credential, provider_key="retell")
    assert first.nonce != second.nonce and first.ciphertext != second.ciphertext
    assert secret.encode() not in first.ciphertext
    assert first.encryption_key_id == LEGACY_ENCRYPTION_KEY_ID
    assert first.encryption_version == CURRENT_ENCRYPTION_VERSION
    assert first.encryption_revision == 0
    assert first.ciphertext.hex() not in repr(first)
    assert first.nonce.hex() not in repr(first)
    clear = service.decrypt(first.ciphertext, first.nonce, company_id=company, connection_id=connection, credential_id=credential, provider_key="retell", encryption_version=first.encryption_version, encryption_key_id=first.encryption_key_id)
    assert clear.secrets == {"api_key":secret} and secret not in repr(clear)


@pytest.mark.parametrize("mutation", ["ciphertext","nonce","identity","key"])
def test_aead_tampering_identity_and_wrong_key_fail_sanitized(mutation: str) -> None:
    company, connection, credential = uuid4(), uuid4(), uuid4()
    service = _encryption_service("11"*32)
    encrypted = service.encrypt({"api_key":"never-echo-this"}, company_id=company, connection_id=connection, credential_id=credential, provider_key="retell")
    ciphertext, nonce = encrypted.ciphertext, encrypted.nonce
    target = _encryption_service("22"*32) if mutation == "key" else service
    provider_key = "twilio" if mutation == "identity" else "retell"
    if mutation == "ciphertext": ciphertext = bytes([ciphertext[0]^1])+ciphertext[1:]
    if mutation == "nonce": nonce = bytes([nonce[0]^1])+nonce[1:]
    with pytest.raises(CredentialEncryptionError) as error:
        target.decrypt(ciphertext, nonce, company_id=company, connection_id=connection, credential_id=credential, provider_key=provider_key, encryption_version=2, encryption_key_id="legacy")
    assert "never-echo-this" not in str(error.value)


def test_aad_v1_is_byte_compatible_and_v2_binds_key_id() -> None:
    company, connection, credential = uuid4(), uuid4(), uuid4()
    legacy = credential_aad(company_id=company, connection_id=connection, credential_id=credential, provider_key="retell", encryption_version=1)
    assert legacy == f"company-ai/provider-credential/v1/{company}/{connection}/{credential}/retell".encode()
    assert credential_aad(company_id=company, connection_id=connection, credential_id=credential, provider_key="retell", encryption_version=1, encryption_key_id="legacy") == legacy
    first = credential_aad(company_id=company, connection_id=connection, credential_id=credential, provider_key="retell", encryption_version=2, encryption_key_id="legacy")
    second = credential_aad(company_id=company, connection_id=connection, credential_id=credential, provider_key="retell", encryption_version=2, encryption_key_id="previous")
    assert first != second and b"/v2/legacy/" in first


@pytest.mark.parametrize("stored_key_id", [None, "legacy"])
def test_historical_v1_credentials_remain_readable(
    stored_key_id: str | None,
) -> None:
    key = bytes([31]) * 32
    company, connection, credential = uuid4(), uuid4(), uuid4()
    aad = credential_aad(company_id=company, connection_id=connection, credential_id=credential, provider_key="retell", encryption_version=1)
    nonce = bytes(range(12))
    ciphertext = AESGCM(key).encrypt(
        nonce,
        json.dumps({"api_key": "historical"}, separators=(",", ":")).encode(),
        aad,
    )
    clear = _encryption_service(key.hex()).decrypt(
        ciphertext,
        nonce,
        company_id=company,
        connection_id=connection,
        credential_id=credential,
        provider_key="retell",
        encryption_version=1,
        encryption_key_id=stored_key_id,
    )
    assert clear.secrets == {"api_key": "historical"}


@pytest.mark.parametrize(
    "stored_key_id",
    [None, "unknown", "INVALID"],
    ids=["missing", "unknown", "malformed"],
)
def test_v2_missing_unknown_or_malformed_key_id_fails_closed(
    stored_key_id: str | None,
) -> None:
    service = _encryption_service()
    company, connection, credential = uuid4(), uuid4(), uuid4()
    encrypted = service.encrypt({"api_key": "redacted"}, company_id=company, connection_id=connection, credential_id=credential, provider_key="retell")
    with pytest.raises(CredentialEncryptionError) as error:
        service.decrypt(encrypted.ciphertext, encrypted.nonce, company_id=company, connection_id=connection, credential_id=credential, provider_key="retell", encryption_version=2, encryption_key_id=stored_key_id)
    assert str(error.value) == "Credential decryption failed."
    assert "redacted" not in str(error.value)


def test_v2_changed_known_key_id_fails_authenticated_decryption() -> None:
    keyring = parse_encryption_keyring(
        json.dumps({"legacy": "33" * 32, "previous": "44" * 32}),
        active_key_id="legacy",
    )
    service = CredentialEncryptionService(keyring)
    company, connection, credential = uuid4(), uuid4(), uuid4()
    encrypted = service.encrypt({"api_key": "redacted"}, company_id=company, connection_id=connection, credential_id=credential, provider_key="retell")
    with pytest.raises(CredentialEncryptionError) as error:
        service.decrypt(encrypted.ciphertext, encrypted.nonce, company_id=company, connection_id=connection, credential_id=credential, provider_key="retell", encryption_version=2, encryption_key_id="previous")
    assert str(error.value) == "Credential decryption failed."


def test_previous_keys_decrypt_v1_and_v2_credentials() -> None:
    keyring = parse_encryption_keyring(
        json.dumps({"current": "55" * 32, "previous": "66" * 32}),
        active_key_id="previous",
    )
    previous_service = CredentialEncryptionService(keyring)
    company, connection, credential = uuid4(), uuid4(), uuid4()
    encrypted = previous_service.encrypt(
        {"api_key": "previous-value"},
        company_id=company,
        connection_id=connection,
        credential_id=credential,
        provider_key="retell",
    )
    runtime_service = CredentialEncryptionService(
        parse_encryption_keyring(
            json.dumps({"current": "55" * 32, "previous": "66" * 32}),
            active_key_id="current",
        )
    )
    assert runtime_service.decrypt(
        encrypted.ciphertext,
        encrypted.nonce,
        company_id=company,
        connection_id=connection,
        credential_id=credential,
        provider_key="retell",
        encryption_version=2,
        encryption_key_id="previous",
    ).secrets == {"api_key": "previous-value"}

    aad = credential_aad(
        company_id=company,
        connection_id=connection,
        credential_id=credential,
        provider_key="retell",
        encryption_version=1,
    )
    nonce = bytes(range(12))
    ciphertext = AESGCM(bytes([0x66]) * 32).encrypt(
        nonce,
        b'{"api_key":"historical"}',
        aad,
    )
    assert runtime_service.decrypt(
        ciphertext,
        nonce,
        company_id=company,
        connection_id=connection,
        credential_id=credential,
        provider_key="retell",
        encryption_version=1,
        encryption_key_id="previous",
    ).secrets == {"api_key": "historical"}


def test_v1_null_key_id_requires_explicit_legacy_entry() -> None:
    service = _encryption_service("77" * 32, active_key_id="current")
    with pytest.raises(CredentialEncryptionError) as error:
        service.decrypt(
            b"ciphertext",
            bytes(range(12)),
            company_id=uuid4(),
            connection_id=uuid4(),
            credential_id=uuid4(),
            provider_key="retell",
            encryption_version=1,
            encryption_key_id=None,
        )

    assert str(error.value) == "Credential decryption failed."


def test_strict_key_decoding() -> None:
    assert len(decode_encryption_key("ab"*32)) == 32
    assert len(decode_encryption_key(base64.urlsafe_b64encode(b"x"*32).decode())) == 32
    for value in ("","passphrase","ab"*31):
        with pytest.raises(CredentialEncryptionError): decode_encryption_key(value)


def test_database_company_integrity_repr_and_restrict() -> None:
    assert "uq_provider_connections_company_id" in {x.name for x in ProviderConnection.__table__.constraints}
    names = {x.name for x in ProviderCredential.__table__.constraints}
    assert {"fk_provider_credentials_company_connection","fk_provider_credentials_rotation","ck_provider_credentials_encryption_key_id","ck_provider_credentials_encryption_revision"} <= names
    columns = ProviderCredential.__table__.columns
    assert columns.encryption_key_id.nullable is False
    assert columns.encryption_key_id.type.length == 64
    assert columns.encryption_revision.nullable is False
    assert str(columns.encryption_revision.server_default.arg) == "0"
    index = next(item for item in ProviderCredential.__table__.indexes if item.name == "ix_provider_credentials_encryption_key_id_id")
    assert tuple(column.name for column in index.columns) == ("encryption_key_id", "id")
    assert all(fk.ondelete=="RESTRICT" for model in (ProviderConnection,ProviderCredential) for fk in model.__table__.foreign_keys)
    item = ProviderCredential(id=uuid4(),company_id=uuid4(),provider_connection_id=uuid4(),encrypted_payload=b"secret-ciphertext",nonce=b"123456789012")
    assert "secret-ciphertext" not in repr(item) and "123456789012" not in repr(item)


def test_provider_rbac_audit_and_safe_openapi() -> None:
    for role in ("owner","admin"): assert role_has_permission(role,CompanyPermission.PROVIDERS_MANAGE)
    for role in ("operator","viewer"):
        assert role_has_permission(role,CompanyPermission.PROVIDERS_READ)
        assert not role_has_permission(role,CompanyPermission.PROVIDERS_MANAGE)
    actions = {f"provider_connection.{x}" for x in ("created","updated","activated","deactivated","revoked")} | {f"provider_credential.{x}" for x in ("created","rotated","revoked")}
    assert {AuditAction(x).value for x in actions} == actions
    paths = app.openapi()["paths"]
    assert "/api/v1/provider-types" in paths and "/api/v1/companies/{company_id}/provider-connections/{connection_id}/credentials" in paths
    assert all("delete" not in operations for path,operations in paths.items() if "provider" in path)
    schema = str(app.openapi())
    for field in ("encryption_key_id", "encryption_revision", "encrypted_payload", "'nonce'", "keyring"):
        assert field not in schema


def test_local_test_email_setup_is_development_only_idempotent_and_credentialless() -> None:
    company_id, connection_id, actor_id = uuid4(), uuid4(), uuid4()
    repository = Mock()
    repository.connection_by_slug.side_effect = [
        None,
        ProviderConnection(
            id=connection_id,
            company_id=company_id,
            provider_key="local_test_email",
            display_name="Local Test Email Provider",
            slug="local-test-email",
            authentication_type="none",
            status="active",
            configuration={},
            metadata_={"development_only": True, "live_delivery": False},
            created_by_administrator_id=actor_id,
            activated_by_administrator_id=actor_id,
        ),
    ]
    repository.create_connection.side_effect = lambda **values: ProviderConnection(id=connection_id, **values)
    audit = Mock()
    session = Mock()
    service = ProviderConnectionService(repository, audit, session, _encryption_service())

    first = service.setup_local_test_email_connection(company_id=company_id, actor=SimpleNamespace(id=actor_id), app_environment="development")
    second = service.setup_local_test_email_connection(company_id=company_id, actor=SimpleNamespace(id=actor_id), app_environment="development")

    assert first.id == second.id == connection_id
    assert first.provider_key == "local_test_email"
    assert first.status == "active"
    assert first.authentication_type == "none"
    assert first.configuration == {}
    assert first.metadata_ == {"development_only": True, "live_delivery": False}
    assert repository.create_credential.call_count == 0
    assert repository.active_credential.call_count == 0
    assert audit.append_company_event.call_count == 1
    details = audit.append_company_event.call_args.kwargs["details"]
    assert details["development_only"] is True
    assert details["live_delivery"] is False


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_local_test_email_setup_fails_closed_outside_non_production(environment: str) -> None:
    service = ProviderConnectionService(Mock(), Mock(), Mock(), _encryption_service())
    with pytest.raises(ProviderLifecycleError):
        service.setup_local_test_email_connection(company_id=uuid4(), actor=SimpleNamespace(id=uuid4()), app_environment=environment)


def test_credential_rotation_uses_v2_key_metadata_and_safe_audit() -> None:
    company_id, connection_id, old_id, actor_id = uuid4(), uuid4(), uuid4(), uuid4()
    connection = ProviderConnection(
        id=connection_id,
        company_id=company_id,
        provider_key="retell",
        display_name="Primary",
        slug="primary",
        authentication_type="api_key",
        status="inactive",
    )
    old = ProviderCredential(
        id=old_id,
        company_id=company_id,
        provider_connection_id=connection_id,
        status="active",
        encrypted_payload=b"old-ciphertext",
        nonce=b"123456789012",
        encryption_version=1,
    )
    repository = Mock()
    repository.connection.return_value = connection
    repository.credential.return_value = old
    repository.save_credential.side_effect = lambda item: item
    repository.create_credential.side_effect = lambda **values: ProviderCredential(**values)
    audit = Mock()
    session = Mock()
    service = ProviderConnectionService(
        repository,
        audit,
        session,
        _encryption_service(active_key_id="current"),
    )

    new = service.rotate_credential(
        company_id=company_id,
        connection_id=connection_id,
        credential_id=old_id,
        data=ProviderCredentialCreate(secrets={"api_key": "never-log-this"}),
        actor=SimpleNamespace(id=actor_id),
    )

    assert old.status == "rotated"
    assert new.encryption_version == 2
    assert new.encryption_key_id == "current"
    assert new.encryption_revision == 0
    assert new.rotated_from_credential_id == old_id
    details = audit.append_company_event.call_args.kwargs["details"]
    assert details["encryption_version"] == 2
    assert details["encryption_key_id"] == "current"
    assert details["encryption_revision"] == 0
    serialized = repr(details)
    for forbidden in ("never-log-this", "old-ciphertext", "nonce", "api_key"):
        assert forbidden not in serialized


def test_service_resolution_uses_stored_version_and_key_id() -> None:
    company_id, connection_id, credential_id = uuid4(), uuid4(), uuid4()
    encryption = _encryption_service()
    encrypted = encryption.encrypt(
        {"api_key": "resolved-value"},
        company_id=company_id,
        connection_id=connection_id,
        credential_id=credential_id,
        provider_key="retell",
    )
    connection = ProviderConnection(
        id=connection_id,
        company_id=company_id,
        provider_key="retell",
        display_name="Primary",
        slug="primary",
        authentication_type="api_key",
        status="active",
    )
    credential = ProviderCredential(
        id=credential_id,
        company_id=company_id,
        provider_connection_id=connection_id,
        status="active",
        encrypted_payload=encrypted.ciphertext,
        nonce=encrypted.nonce,
        encryption_version=encrypted.encryption_version,
        encryption_key_id=encrypted.encryption_key_id,
        encryption_revision=encrypted.encryption_revision,
    )
    repository = Mock()
    repository.connection.return_value = connection
    repository.company.return_value = SimpleNamespace(
        is_active=True,
        status="active",
    )
    repository.active_credential.return_value = credential
    service = ProviderConnectionService(
        repository,
        Mock(),
        Mock(),
        encryption,
    )

    resolved = service.resolve(
        company_id=company_id,
        connection_id=connection_id,
        provider_key="retell",
    )

    assert resolved.secret_bundle.secrets == {"api_key": "resolved-value"}
    assert "resolved-value" not in repr(resolved)
