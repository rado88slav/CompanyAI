"""Narrow AES-256-GCM provider credential encryption boundary."""

import base64
import binascii
from dataclasses import dataclass
import json
import os
from typing import Any
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CredentialEncryptionError(Exception):
    """Sanitized credential encryption failure."""


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
        raise CredentialEncryptionError("Credential encryption configuration is invalid.") from exc
    if len(key) != 32:
        raise CredentialEncryptionError("Credential encryption configuration is invalid.")
    return key


def credential_aad(*, company_id: UUID, connection_id: UUID, credential_id: UUID, provider_key: str, encryption_version: int) -> bytes:
    return f"company-ai/provider-credential/v{encryption_version}/{company_id}/{connection_id}/{credential_id}/{provider_key}".encode()


@dataclass(slots=True)
class DecryptedCredential:
    secrets: dict[str, Any]

    def __repr__(self) -> str:
        return "DecryptedCredential(secrets=**********)"


class CredentialEncryptionService:
    def __init__(self, encoded_key: str) -> None:
        self._key = decode_encryption_key(encoded_key)

    def encrypt(self, secrets: dict[str, Any], *, associated_data: bytes) -> tuple[bytes, bytes]:
        nonce = os.urandom(12)
        plaintext = bytearray(json.dumps(secrets, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())
        try:
            return AESGCM(self._key).encrypt(nonce, bytes(plaintext), associated_data), nonce
        except Exception as exc:
            raise CredentialEncryptionError("Credential encryption failed.") from exc
        finally:
            plaintext[:] = b"\x00" * len(plaintext)

    def decrypt(self, ciphertext: bytes, nonce: bytes, *, associated_data: bytes) -> DecryptedCredential:
        try:
            plaintext = bytearray(AESGCM(self._key).decrypt(nonce, ciphertext, associated_data))
            value = json.loads(plaintext)
            if not isinstance(value, dict):
                raise ValueError
            return DecryptedCredential(value)
        except (InvalidTag, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise CredentialEncryptionError("Credential decryption failed.") from exc
        finally:
            if "plaintext" in locals():
                plaintext[:] = b"\x00" * len(plaintext)
