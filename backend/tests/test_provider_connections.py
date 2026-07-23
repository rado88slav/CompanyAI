"""Focused Provider Connections security and contract tests."""
import base64
from uuid import uuid4
import pytest
from pydantic import ValidationError

from app.core.company_permissions import CompanyPermission, role_has_permission
from app.core.credential_encryption import CredentialEncryptionError, CredentialEncryptionService, credential_aad, decode_encryption_key
from app.core.provider_connections import ProviderDescriptor, ProviderRegistry, provider_registry, validate_safe_object
from app.main import app
from app.models.audit_log import AuditAction
from app.models.provider_connection import ProviderConnection, ProviderCredential
from app.schemas.provider_connection import ProviderConnectionCreate, ProviderCredentialCreate


def test_eight_immutable_builtin_descriptors() -> None:
    assert {x.key for x in provider_registry.all()} == {"retell","twilio","telnyx","microsoft_365","google_workspace","lemlist","instantly","smartlead"}
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
    service = CredentialEncryptionService("00"*32)
    company, connection, credential = uuid4(), uuid4(), uuid4()
    aad = credential_aad(company_id=company,connection_id=connection,credential_id=credential,provider_key="retell",encryption_version=1)
    secret = "plaintext-provider-secret"
    first, nonce1 = service.encrypt({"api_key":secret},associated_data=aad)
    second, nonce2 = service.encrypt({"api_key":secret},associated_data=aad)
    assert nonce1 != nonce2 and first != second and secret.encode() not in first
    clear = service.decrypt(first,nonce1,associated_data=aad)
    assert clear.secrets == {"api_key":secret} and secret not in repr(clear)


@pytest.mark.parametrize("mutation", ["ciphertext","nonce","aad","key"])
def test_aead_tampering_identity_and_wrong_key_fail_sanitized(mutation: str) -> None:
    company, connection, credential = uuid4(), uuid4(), uuid4()
    aad = credential_aad(company_id=company,connection_id=connection,credential_id=credential,provider_key="retell",encryption_version=1)
    service = CredentialEncryptionService("11"*32)
    ciphertext, nonce = service.encrypt({"api_key":"never-echo-this"},associated_data=aad)
    target = CredentialEncryptionService("22"*32) if mutation == "key" else service
    if mutation == "ciphertext": ciphertext = bytes([ciphertext[0]^1])+ciphertext[1:]
    if mutation == "nonce": nonce = bytes([nonce[0]^1])+nonce[1:]
    if mutation == "aad": aad += b"/other"
    with pytest.raises(CredentialEncryptionError) as error: target.decrypt(ciphertext,nonce,associated_data=aad)
    assert "never-echo-this" not in str(error.value)


def test_strict_key_decoding() -> None:
    assert len(decode_encryption_key("ab"*32)) == 32
    assert len(decode_encryption_key(base64.urlsafe_b64encode(b"x"*32).decode())) == 32
    for value in ("","passphrase","ab"*31):
        with pytest.raises(CredentialEncryptionError): decode_encryption_key(value)


def test_database_company_integrity_repr_and_restrict() -> None:
    assert "uq_provider_connections_company_id" in {x.name for x in ProviderConnection.__table__.constraints}
    names = {x.name for x in ProviderCredential.__table__.constraints}
    assert {"fk_provider_credentials_company_connection","fk_provider_credentials_rotation"} <= names
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
    assert "encrypted_payload" not in schema and "'nonce'" not in schema
