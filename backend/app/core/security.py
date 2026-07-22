"""Password hashing and signed access-token helpers."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"

_password_hash = PasswordHash.recommended()


class SecurityConfigurationError(RuntimeError):
    """Raised when authentication security is not configured safely."""


class InvalidAccessTokenError(ValueError):
    """Raised when an access token cannot be trusted."""


def _validate_secret_key(secret_key: str) -> None:
    """Require a sufficiently long signing secret."""

    if len(secret_key) < 32:
        raise SecurityConfigurationError(
            "APP_SECRET_KEY must contain at least 32 characters."
        )


def hash_password(password: str) -> str:
    """Create an Argon2 password hash."""

    return _password_hash.hash(password)


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:
    """Verify a plaintext password against its stored hash."""

    return _password_hash.verify(
        plain_password,
        password_hash,
    )


def create_access_token(
    administrator_id: UUID,
    *,
    secret_key: str,
    expires_minutes: int,
) -> str:
    """Create a signed administrator access token."""

    _validate_secret_key(secret_key)

    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(
        minutes=expires_minutes,
    )

    payload = {
        "sub": str(administrator_id),
        "type": ACCESS_TOKEN_TYPE,
        "iat": issued_at,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        secret_key,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(
    token: str,
    *,
    secret_key: str,
) -> UUID:
    """Validate an access token and return its administrator UUID."""

    _validate_secret_key(secret_key)

    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[JWT_ALGORITHM],
            options={
                "require": [
                    "sub",
                    "type",
                    "iat",
                    "exp",
                ],
            },
        )

        if payload.get("type") != ACCESS_TOKEN_TYPE:
            raise InvalidAccessTokenError(
                "Unexpected token type."
            )

        subject = payload.get("sub")

        if not isinstance(subject, str):
            raise InvalidAccessTokenError(
                "Token subject is invalid."
            )

        return UUID(subject)
    except (
        jwt.InvalidTokenError,
        ValueError,
        TypeError,
    ) as exc:
        raise InvalidAccessTokenError(
            "Access token is invalid."
        ) from exc
