"""Machine credential and short-lived agent JWT security primitives."""

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt

from app.core.security import SecurityConfigurationError

CREDENTIAL_PREFIX = "cai_agent_v1_"
AGENT_TOKEN_TYPE = "agent"


class InvalidAgentCredentialError(ValueError): pass
class InvalidAgentTokenError(ValueError): pass


@dataclass(frozen=True, slots=True)
class GeneratedAgentCredential:
    plaintext: str
    public_id: str
    secret_hash: str
    secret_prefix: str
    secret_last_four: str


@dataclass(frozen=True, slots=True)
class AgentTokenClaims:
    agent_id: UUID
    company_id: UUID
    credential_id: UUID
    auth_version: int


def _require_secret(value: str, name: str) -> None:
    if len(value) < 32:
        raise SecurityConfigurationError(f"{name} must contain at least 32 characters.")


def _hash_secret(secret: str, pepper: str) -> str:
    _require_secret(pepper, "AGENT_CREDENTIAL_PEPPER")
    return hmac.new(pepper.encode(), secret.encode(), hashlib.sha256).hexdigest()


def generate_agent_credential(*, pepper: str) -> GeneratedAgentCredential:
    public_id = secrets.token_hex(12)
    secret = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    plaintext = f"{CREDENTIAL_PREFIX}{public_id}.{secret}"
    return GeneratedAgentCredential(plaintext, public_id, _hash_secret(secret, pepper), plaintext[:24], secret[-4:])


def parse_agent_credential(value: str) -> tuple[str, str]:
    if not value.startswith(CREDENTIAL_PREFIX) or value.count(".") != 1:
        raise InvalidAgentCredentialError
    public_part, secret = value.split(".", 1)
    public_id = public_part[len(CREDENTIAL_PREFIX):]
    if len(public_id) != 24 or len(secret) < 43:
        raise InvalidAgentCredentialError
    return public_id, secret


def verify_agent_credential(value: str, expected_hash: str, *, pepper: str) -> bool:
    try:
        _, secret = parse_agent_credential(value)
        candidate = _hash_secret(secret, pepper)
    except (InvalidAgentCredentialError, SecurityConfigurationError):
        raise
    return hmac.compare_digest(candidate, expected_hash)


def create_agent_token(*, agent_id: UUID, company_id: UUID, credential_id: UUID, auth_version: int, secret: str, algorithm: str, ttl_seconds: int, issuer: str, audience: str) -> str:
    _require_secret(secret, "AGENT_JWT_SECRET")
    now = datetime.now(UTC)
    payload = {"sub": str(agent_id), "token_type": AGENT_TOKEN_TYPE, "company_id": str(company_id), "credential_id": str(credential_id), "auth_version": auth_version, "iss": issuer, "aud": audience, "iat": now, "exp": now + timedelta(seconds=ttl_seconds), "jti": str(uuid4())}
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_agent_token(token: str, *, secret: str, algorithm: str, issuer: str, audience: str) -> AgentTokenClaims:
    _require_secret(secret, "AGENT_JWT_SECRET")
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm], issuer=issuer, audience=audience, options={"require": ["sub", "token_type", "company_id", "credential_id", "auth_version", "iss", "aud", "iat", "exp", "jti"]})
        if payload.get("token_type") != AGENT_TOKEN_TYPE or not isinstance(payload.get("auth_version"), int) or payload["auth_version"] <= 0:
            raise InvalidAgentTokenError
        return AgentTokenClaims(UUID(payload["sub"]), UUID(payload["company_id"]), UUID(payload["credential_id"]), payload["auth_version"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise InvalidAgentTokenError from exc
