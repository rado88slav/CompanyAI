"""Narrow AES-256-GCM provider credential encryption boundary."""

import base64
import binascii
from collections.abc import Mapping
from dataclasses import dataclass, field as dataclass_field
import hmac
import json
import os
import re
from types import MappingProxyType
from typing import Any
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CredentialEncryptionError(Exception):
    """Sanitized credential encryption failure."""


_CONFIGURATION_ERROR = "Credential encryption configuration is invalid."
_ENCRYPTION_ERROR = "Credential encryption failed."
_DECRYPTION_ERROR = "Credential decryption failed."
_KEY_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
LEGACY_ENCRYPTION_KEY_ID = "legacy"
LEGACY_ENCRYPTION_VERSION = 1
CURRENT_ENCRYPTION_VERSION = 2
CURRENT_ENCRYPTION_REVISION = 0


def decode_encryption_key(value: str) -> bytes:
    try:
        if len(value) == 64:
            key = bytes.fromhex(value)
        else:
            raw = value.encode("ascii")
            if len(raw) != 44:
                raise ValueError
            key = base64.b64decode(raw, altchars=b"-_", validate=True)
    except (ValueError, UnicodeError, binascii.Error) as exc:
        raise CredentialEncryptionError(_CONFIGURATION_ERROR) from exc
    if len(key) != 32:
        raise CredentialEncryptionError(_CONFIGURATION_ERROR)
    return key


@dataclass(frozen=True, slots=True)
class CredentialEncryptionKeyMetadata:
    """Non-secret immutable metadata for one configured key."""

    key_id: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class CredentialEncryptionKeyring:
    """Immutable validated credential-encryption keyring."""

    _active_key_id: str
    _keys: Mapping[str, bytes] = dataclass_field(repr=False)
    _metadata: tuple[CredentialEncryptionKeyMetadata, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_keys",
            MappingProxyType(dict(self._keys)),
        )
        object.__setattr__(self, "_metadata", tuple(self._metadata))

    @property
    def active_key_id(self) -> str:
        return self._active_key_id

    @property
    def active_key_material(self) -> bytes:
        return self._keys[self._active_key_id]

    @property
    def key_ids(self) -> tuple[str, ...]:
        return tuple(item.key_id for item in self._metadata)

    @property
    def metadata(self) -> tuple[CredentialEncryptionKeyMetadata, ...]:
        return self._metadata

    def decryption_key(self, key_id: str) -> bytes:
        if not isinstance(key_id, str) or not _KEY_ID_PATTERN.fullmatch(key_id):
            raise CredentialEncryptionError(_CONFIGURATION_ERROR)
        material = self._keys.get(key_id)
        if material is None:
            raise CredentialEncryptionError(_CONFIGURATION_ERROR)
        return material


def _unique_json_object(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _parse_encryption_keyring(
    encoded_keyring: str,
    *,
    active_key_id: str | None,
) -> CredentialEncryptionKeyring:
    if not isinstance(encoded_keyring, str):
        raise ValueError
    parsed = json.loads(
        encoded_keyring,
        object_pairs_hook=_unique_json_object,
    )
    if not isinstance(parsed, dict) or not parsed:
        raise ValueError
    if (
        not isinstance(active_key_id, str)
        or not _KEY_ID_PATTERN.fullmatch(active_key_id)
    ):
        raise ValueError

    decoded: dict[str, bytes] = {}
    materials: list[bytes] = []
    for key_id, encoded_key in parsed.items():
        if (
            not isinstance(key_id, str)
            or not _KEY_ID_PATTERN.fullmatch(key_id)
            or not isinstance(encoded_key, str)
        ):
            raise ValueError
        material = decode_encryption_key(encoded_key)
        if any(
            hmac.compare_digest(material, existing)
            for existing in materials
        ):
            raise ValueError
        decoded[key_id] = material
        materials.append(material)

    if active_key_id not in decoded:
        raise ValueError

    key_ids = tuple(sorted(decoded))
    metadata = tuple(
        CredentialEncryptionKeyMetadata(
            key_id=key_id,
            is_active=key_id == active_key_id,
        )
        for key_id in key_ids
    )
    return CredentialEncryptionKeyring(
        _active_key_id=active_key_id,
        _keys=decoded,
        _metadata=metadata,
    )


def parse_encryption_keyring(
    encoded_keyring: str,
    *,
    active_key_id: str | None,
) -> CredentialEncryptionKeyring:
    """Parse and validate a JSON keyring without exposing key material."""

    try:
        return _parse_encryption_keyring(
            encoded_keyring,
            active_key_id=active_key_id,
        )
    except (
        CredentialEncryptionError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ):
        pass
    raise CredentialEncryptionError(_CONFIGURATION_ERROR) from None


def parse_runtime_encryption_keyring(
    encoded_keyring: str,
    *,
    active_key_id: str | None,
    legacy_key_configured: bool,
) -> CredentialEncryptionKeyring:
    """Validate the unambiguous runtime keyring configuration."""

    if legacy_key_configured:
        raise CredentialEncryptionError(_CONFIGURATION_ERROR)
    return parse_encryption_keyring(
        encoded_keyring,
        active_key_id=active_key_id,
    )


def credential_aad(
    *,
    company_id: UUID,
    connection_id: UUID,
    credential_id: UUID,
    provider_key: str,
    encryption_version: int,
    encryption_key_id: str | None = None,
) -> bytes:
    if encryption_version == LEGACY_ENCRYPTION_VERSION:
        value = (
            f"company-ai/provider-credential/v1/{company_id}/"
            f"{connection_id}/{credential_id}/{provider_key}"
        )
    elif (
        encryption_version == CURRENT_ENCRYPTION_VERSION
        and isinstance(encryption_key_id, str)
        and _KEY_ID_PATTERN.fullmatch(encryption_key_id)
    ):
        value = (
            f"company-ai/provider-credential/v2/{encryption_key_id}/"
            f"{company_id}/{connection_id}/{credential_id}/{provider_key}"
        )
    else:
        raise CredentialEncryptionError(_DECRYPTION_ERROR)
    return value.encode("utf-8")


@dataclass(slots=True)
class DecryptedCredential:
    secrets: dict[str, Any]

    def __repr__(self) -> str:
        return "DecryptedCredential(secrets=**********)"


@dataclass(frozen=True, slots=True)
class EncryptedCredential:
    ciphertext: bytes = dataclass_field(repr=False)
    nonce: bytes = dataclass_field(repr=False)
    encryption_version: int
    encryption_key_id: str
    encryption_revision: int


class CredentialEncryptionService:
    def __init__(self, keyring: CredentialEncryptionKeyring) -> None:
        self._keyring = keyring

    @property
    def active_key_id(self) -> str:
        return self._keyring.active_key_id

    def encrypt(
        self,
        secrets: dict[str, Any],
        *,
        company_id: UUID,
        connection_id: UUID,
        credential_id: UUID,
        provider_key: str,
    ) -> EncryptedCredential:
        key_id = self._keyring.active_key_id
        associated_data = credential_aad(
            company_id=company_id,
            connection_id=connection_id,
            credential_id=credential_id,
            provider_key=provider_key,
            encryption_version=CURRENT_ENCRYPTION_VERSION,
            encryption_key_id=key_id,
        )
        nonce = os.urandom(12)
        plaintext = bytearray(json.dumps(secrets, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())
        try:
            ciphertext = AESGCM(
                self._keyring.active_key_material
            ).encrypt(nonce, bytes(plaintext), associated_data)
            return EncryptedCredential(
                ciphertext=ciphertext,
                nonce=nonce,
                encryption_version=CURRENT_ENCRYPTION_VERSION,
                encryption_key_id=key_id,
                encryption_revision=CURRENT_ENCRYPTION_REVISION,
            )
        except Exception as exc:
            raise CredentialEncryptionError(_ENCRYPTION_ERROR) from exc
        finally:
            plaintext[:] = b"\x00" * len(plaintext)

    def decrypt(
        self,
        ciphertext: bytes,
        nonce: bytes,
        *,
        company_id: UUID,
        connection_id: UUID,
        credential_id: UUID,
        provider_key: str,
        encryption_version: int,
        encryption_key_id: str | None,
    ) -> DecryptedCredential:
        try:
            if encryption_version == LEGACY_ENCRYPTION_VERSION:
                key_id = (
                    LEGACY_ENCRYPTION_KEY_ID
                    if encryption_key_id is None
                    else encryption_key_id
                )
            elif (
                encryption_version == CURRENT_ENCRYPTION_VERSION
                and encryption_key_id is not None
            ):
                key_id = encryption_key_id
            else:
                raise CredentialEncryptionError(_DECRYPTION_ERROR)
            key = self._keyring.decryption_key(key_id)
            associated_data = credential_aad(
                company_id=company_id,
                connection_id=connection_id,
                credential_id=credential_id,
                provider_key=provider_key,
                encryption_version=encryption_version,
                encryption_key_id=encryption_key_id,
            )
            plaintext = bytearray(
                AESGCM(key).decrypt(nonce, ciphertext, associated_data)
            )
            value = json.loads(plaintext)
            if not isinstance(value, dict):
                raise ValueError
            return DecryptedCredential(value)
        except (
            CredentialEncryptionError,
            InvalidTag,
            ValueError,
            TypeError,
            json.JSONDecodeError,
        ):
            raise CredentialEncryptionError(_DECRYPTION_ERROR) from None
        finally:
            if "plaintext" in locals():
                plaintext[:] = b"\x00" * len(plaintext)
