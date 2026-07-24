"""Fail-fast application startup configuration tests."""

import base64

import pytest

from app.core.config import get_settings
from app.core.credential_encryption import CredentialEncryptionError
from app.main import create_application


def _create_application_with_key(
    monkeypatch: pytest.MonkeyPatch,
    value: str | None,
) -> None:
    if value is None:
        monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEY", raising=False)
    else:
        monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", value)

    get_settings.cache_clear()
    try:
        create_application()
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize(
    "encoded_key",
    [
        "a1" * 32,
        base64.urlsafe_b64encode(bytes(range(32))).decode("ascii"),
    ],
    ids=["hex", "padded-base64url"],
)
def test_valid_credential_encryption_key_allows_application_creation(
    monkeypatch: pytest.MonkeyPatch,
    encoded_key: str,
) -> None:
    _create_application_with_key(monkeypatch, encoded_key)


@pytest.mark.parametrize(
    "invalid_key",
    [
        None,
        "",
        "correct-horse-battery-staple",
        "!" * 44,
        base64.urlsafe_b64encode(bytes(range(31))).decode("ascii"),
        base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")[:-2] + "=A",
    ],
    ids=[
        "missing",
        "empty",
        "passphrase",
        "invalid-base64",
        "wrong-decoded-length",
        "malformed-padding",
    ],
)
def test_invalid_credential_encryption_key_fails_during_application_creation(
    monkeypatch: pytest.MonkeyPatch,
    invalid_key: str | None,
) -> None:
    with pytest.raises(CredentialEncryptionError) as error:
        _create_application_with_key(monkeypatch, invalid_key)

    assert str(error.value) == "Credential encryption configuration is invalid."
    if invalid_key:
        assert invalid_key not in str(error.value)


def test_startup_configuration_error_does_not_expose_secret_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid_value = "invalid-credential-encryption-material"
    forbidden_material = (
        invalid_value,
        "b2" * 32,
        "ciphertext-material",
        "nonce-material",
        "provider-secret-payload",
    )

    with pytest.raises(CredentialEncryptionError) as error:
        _create_application_with_key(monkeypatch, invalid_value)

    message = str(error.value)
    assert message == "Credential encryption configuration is invalid."
    assert all(value not in message for value in forbidden_material)
