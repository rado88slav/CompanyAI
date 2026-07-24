"""Fail-fast runtime credential-encryption keyring configuration tests."""

import base64
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.config import get_settings
from app.core.credential_encryption import CredentialEncryptionError
from app.main import create_application
from app.services.provider_connection import get_provider_connection_service

CONFIGURATION_ERROR = "Credential encryption configuration is invalid."
ACTIVE_ID_ENV = "CREDENTIAL_ENCRYPTION_ACTIVE_KEY_ID"
KEYRING_ENV = "CREDENTIAL_ENCRYPTION_KEYRING"
LEGACY_ENV = "CREDENTIAL_ENCRYPTION_KEY"


def _hex_key(byte: int) -> str:
    return (bytes([byte]) * 32).hex()


def _keyring(entries: dict[str, str]) -> str:
    return json.dumps(entries, separators=(",", ":"))


def _create_application(
    monkeypatch: pytest.MonkeyPatch,
    *,
    active_key_id: str | None,
    encoded_keyring: str | None,
    legacy_key: str | None = None,
):
    for name in (ACTIVE_ID_ENV, KEYRING_ENV, LEGACY_ENV):
        monkeypatch.delenv(name, raising=False)
    if active_key_id is not None:
        monkeypatch.setenv(ACTIVE_ID_ENV, active_key_id)
    if encoded_keyring is not None:
        monkeypatch.setenv(KEYRING_ENV, encoded_keyring)
    if legacy_key is not None:
        monkeypatch.setenv(LEGACY_ENV, legacy_key)

    get_settings.cache_clear()
    try:
        return create_application()
    finally:
        get_settings.cache_clear()


def _assert_sanitized(error: CredentialEncryptionError) -> None:
    assert str(error) == CONFIGURATION_ERROR
    assert error.__cause__ is None
    assert error.__context__ is None


def test_valid_one_key_runtime_configuration_allows_application_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = _create_application(
        monkeypatch,
        active_key_id="primary",
        encoded_keyring=_keyring({"primary": _hex_key(1)}),
    )

    assert application.state.credential_encryption_keyring.active_key_id == "primary"
    assert application.state.credential_encryption_keyring.key_ids == ("primary",)


def test_active_and_previous_runtime_keys_allow_application_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = _create_application(
        monkeypatch,
        active_key_id="active-2",
        encoded_keyring=_keyring(
            {
                "previous": _hex_key(2),
                "active-2": base64.urlsafe_b64encode(
                    bytes([3]) * 32
                ).decode("ascii"),
            }
        ),
    )

    keyring = application.state.credential_encryption_keyring
    assert keyring.active_key_id == "active-2"
    assert keyring.key_ids == ("active-2", "previous")


def test_service_wiring_reuses_application_validated_keyring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = _create_application(
        monkeypatch,
        active_key_id="current",
        encoded_keyring=_keyring(
            {"previous": _hex_key(4), "current": _hex_key(5)}
        ),
    )

    service = get_provider_connection_service(
        SimpleNamespace(app=application),
        Mock(),
    )

    assert service._encryption.active_key_id == "current"
    assert (
        service._encryption._keyring
        is application.state.credential_encryption_keyring
    )


@pytest.mark.parametrize(
    ("active_key_id", "encoded_keyring"),
    [
        (None, _keyring({"primary": _hex_key(6)})),
        ("", _keyring({"primary": _hex_key(6)})),
        ("primary", None),
        ("primary", ""),
        ("missing", _keyring({"primary": _hex_key(6)})),
        (
            "primary",
            (
                f'{{"primary":"{_hex_key(6)}",'
                f'"primary":"{_hex_key(7)}"}}'
            ),
        ),
        ("INVALID", _keyring({"INVALID": _hex_key(6)})),
        ("primary", _keyring({"primary": "not-an-encoded-key"})),
        (
            "primary",
            _keyring(
                {
                    "primary": base64.urlsafe_b64encode(
                        bytes([8]) * 31
                    ).decode("ascii")
                }
            ),
        ),
        (
            "primary",
            _keyring(
                {
                    "primary": _hex_key(9),
                    "alias": base64.urlsafe_b64encode(
                        bytes([9]) * 32
                    ).decode("ascii"),
                }
            ),
        ),
    ],
    ids=[
        "missing-active-id",
        "empty-active-id",
        "missing-keyring",
        "empty-keyring",
        "active-id-absent",
        "duplicate-json-ids",
        "malformed-id",
        "malformed-key",
        "wrong-key-length",
        "duplicate-key-material",
    ],
)
def test_invalid_runtime_keyring_fails_during_application_creation(
    monkeypatch: pytest.MonkeyPatch,
    active_key_id: str | None,
    encoded_keyring: str | None,
) -> None:
    with pytest.raises(CredentialEncryptionError) as error:
        _create_application(
            monkeypatch,
            active_key_id=active_key_id,
            encoded_keyring=encoded_keyring,
        )

    _assert_sanitized(error.value)
    if active_key_id:
        assert active_key_id not in str(error.value)
    if encoded_keyring:
        assert encoded_keyring not in str(error.value)


def test_legacy_only_configuration_fails_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(CredentialEncryptionError) as error:
        _create_application(
            monkeypatch,
            active_key_id=None,
            encoded_keyring=None,
            legacy_key=_hex_key(10),
        )

    _assert_sanitized(error.value)


def test_legacy_plus_new_configuration_fails_as_ambiguous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_keyring = _keyring({"primary": _hex_key(11)})
    legacy_key = _hex_key(12)

    with pytest.raises(CredentialEncryptionError) as error:
        _create_application(
            monkeypatch,
            active_key_id="primary",
            encoded_keyring=raw_keyring,
            legacy_key=legacy_key,
        )

    _assert_sanitized(error.value)
    assert raw_keyring not in str(error.value)
    assert legacy_key not in str(error.value)


def test_invalid_configuration_prevents_health_and_readiness_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(CredentialEncryptionError):
        _create_application(
            monkeypatch,
            active_key_id="primary",
            encoded_keyring="{malformed-json",
        )


def test_runtime_keyring_is_not_exposed_by_settings_repr_or_openapi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_keyring = _keyring({"primary": _hex_key(13)})
    application = _create_application(
        monkeypatch,
        active_key_id="primary",
        encoded_keyring=raw_keyring,
    )
    monkeypatch.setenv(ACTIVE_ID_ENV, "primary")
    monkeypatch.setenv(KEYRING_ENV, raw_keyring)
    monkeypatch.delenv(LEGACY_ENV, raising=False)
    get_settings.cache_clear()
    try:
        assert raw_keyring not in repr(get_settings())
    finally:
        get_settings.cache_clear()

    schema = json.dumps(application.openapi())
    for forbidden in (
        ACTIVE_ID_ENV,
        KEYRING_ENV,
        LEGACY_ENV,
        "credential_encryption_keyring",
        "encryption_key_id",
        "encryption_revision",
    ):
        assert forbidden not in schema
