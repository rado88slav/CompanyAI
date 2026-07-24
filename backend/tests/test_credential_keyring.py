"""Credential-encryption keyring validation and immutability tests."""

import base64
from dataclasses import FrozenInstanceError
import json

import pytest

from app.core.credential_encryption import (
    CredentialEncryptionError,
    CredentialEncryptionKeyMetadata,
    decode_encryption_key,
    parse_encryption_keyring,
)

CONFIGURATION_ERROR = "Credential encryption configuration is invalid."


def _hex_key(byte: int) -> str:
    return (bytes([byte]) * 32).hex()


def _base64_key(byte: int) -> str:
    return base64.b64encode(bytes([byte]) * 32).decode("ascii")


def _base64url_key(byte: int) -> str:
    return base64.urlsafe_b64encode(bytes([byte]) * 32).decode("ascii")


def _keyring_json(entries: dict[str, str]) -> str:
    return json.dumps(entries, separators=(",", ":"))


def _assert_sanitized(error: CredentialEncryptionError) -> None:
    assert str(error) == CONFIGURATION_ERROR
    assert error.__cause__ is None
    assert error.__context__ is None


def test_single_active_keyring_supports_active_and_decryption_lookup() -> None:
    encoded = _hex_key(1)
    keyring = parse_encryption_keyring(
        _keyring_json({"primary": encoded}),
        active_key_id="primary",
    )

    assert keyring.active_key_id == "primary"
    assert keyring.active_key_material == bytes([1]) * 32
    assert keyring.decryption_key("primary") == bytes([1]) * 32
    assert keyring.key_ids == ("primary",)
    assert keyring.metadata == (
        CredentialEncryptionKeyMetadata("primary", True),
    )
    assert encoded not in repr(keyring)


def test_active_and_previous_keys_have_safe_sorted_metadata() -> None:
    keyring = parse_encryption_keyring(
        _keyring_json(
            {
                "previous_1": _base64_key(2),
                "active-2": _base64url_key(3),
            }
        ),
        active_key_id="active-2",
    )

    assert keyring.active_key_id == "active-2"
    assert keyring.active_key_material == bytes([3]) * 32
    assert keyring.decryption_key("previous_1") == bytes([2]) * 32
    assert keyring.key_ids == ("active-2", "previous_1")
    assert keyring.metadata == (
        CredentialEncryptionKeyMetadata("active-2", True),
        CredentialEncryptionKeyMetadata("previous_1", False),
    )


@pytest.mark.parametrize("active_key_id", [None, ""])
def test_missing_or_empty_active_key_id_fails(
    active_key_id: str | None,
) -> None:
    with pytest.raises(CredentialEncryptionError) as error:
        parse_encryption_keyring(
            _keyring_json({"primary": _hex_key(4)}),
            active_key_id=active_key_id,
        )

    _assert_sanitized(error.value)


def test_active_key_id_must_exist_in_keyring() -> None:
    with pytest.raises(CredentialEncryptionError) as error:
        parse_encryption_keyring(
            _keyring_json({"previous": _hex_key(5)}),
            active_key_id="active",
        )

    _assert_sanitized(error.value)


@pytest.mark.parametrize("encoded_keyring", ["{}", "[]", "null", ""])
def test_empty_or_non_object_keyring_fails(encoded_keyring: str) -> None:
    with pytest.raises(CredentialEncryptionError) as error:
        parse_encryption_keyring(
            encoded_keyring,
            active_key_id="primary",
        )

    _assert_sanitized(error.value)


def test_duplicate_json_key_ids_are_rejected() -> None:
    first = _hex_key(6)
    second = _hex_key(7)
    encoded_keyring = (
        f'{{"primary":"{first}","primary":"{second}"}}'
    )

    with pytest.raises(CredentialEncryptionError) as error:
        parse_encryption_keyring(
            encoded_keyring,
            active_key_id="primary",
        )

    _assert_sanitized(error.value)
    assert first not in str(error.value)
    assert second not in str(error.value)


@pytest.mark.parametrize(
    "key_id",
    [
        "Uppercase",
        "1starts-with-number",
        "contains.dot",
        "contains space",
        "a" * 65,
    ],
)
def test_malformed_key_ids_are_rejected(key_id: str) -> None:
    with pytest.raises(CredentialEncryptionError) as error:
        parse_encryption_keyring(
            _keyring_json({key_id: _hex_key(8)}),
            active_key_id=key_id,
        )

    _assert_sanitized(error.value)


@pytest.mark.parametrize(
    "encoded_key",
    [
        "not-an-encoded-key",
        "!" * 44,
        base64.b64encode(bytes([9]) * 31).decode("ascii"),
    ],
    ids=["passphrase", "malformed-base64", "wrong-decoded-length"],
)
def test_invalid_encoded_key_material_is_rejected(
    encoded_key: str,
) -> None:
    with pytest.raises(CredentialEncryptionError) as error:
        parse_encryption_keyring(
            _keyring_json({"primary": encoded_key}),
            active_key_id="primary",
        )

    _assert_sanitized(error.value)
    assert encoded_key not in str(error.value)


def test_duplicate_decoded_key_material_under_different_ids_fails() -> None:
    material = bytes([10]) * 32
    encoded_keyring = _keyring_json(
        {
            "primary": material.hex(),
            "alias": base64.urlsafe_b64encode(material).decode("ascii"),
        }
    )

    with pytest.raises(CredentialEncryptionError) as error:
        parse_encryption_keyring(
            encoded_keyring,
            active_key_id="primary",
        )

    _assert_sanitized(error.value)
    assert material.hex() not in str(error.value)


@pytest.mark.parametrize(
    ("encoded_key", "expected"),
    [
        (_hex_key(11), bytes([11]) * 32),
        (_base64_key(251), bytes([251]) * 32),
        (_base64url_key(251), bytes([251]) * 32),
    ],
    ids=["hex", "padded-base64", "padded-base64url"],
)
def test_supported_key_encodings_use_the_trusted_decoder(
    encoded_key: str,
    expected: bytes,
) -> None:
    assert decode_encryption_key(encoded_key) == expected
    keyring = parse_encryption_keyring(
        _keyring_json({"primary": encoded_key}),
        active_key_id="primary",
    )
    assert keyring.active_key_material == expected


@pytest.mark.parametrize("stored_key_id", ["unknown", "INVALID"])
def test_unknown_or_malformed_stored_key_id_fails_sanitized(
    stored_key_id: str,
) -> None:
    encoded = _hex_key(12)
    keyring = parse_encryption_keyring(
        _keyring_json({"primary": encoded}),
        active_key_id="primary",
    )

    with pytest.raises(CredentialEncryptionError) as error:
        keyring.decryption_key(stored_key_id)

    _assert_sanitized(error.value)
    assert encoded not in str(error.value)


def test_keyring_and_key_metadata_are_immutable() -> None:
    keyring = parse_encryption_keyring(
        _keyring_json({"primary": _hex_key(13)}),
        active_key_id="primary",
    )

    with pytest.raises(FrozenInstanceError):
        keyring._active_key_id = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        keyring._keys["other"] = bytes([14]) * 32  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        keyring.metadata[0].key_id = "changed"  # type: ignore[misc]


def test_errors_never_include_key_values_or_json_content() -> None:
    exposed_value = "sensitive-invalid-key-material"
    encoded_keyring = _keyring_json({"primary": exposed_value})

    with pytest.raises(CredentialEncryptionError) as error:
        parse_encryption_keyring(
            encoded_keyring,
            active_key_id="primary",
        )

    _assert_sanitized(error.value)
    message = str(error.value)
    assert exposed_value not in message
    assert encoded_keyring not in message
    assert _hex_key(15) not in message
