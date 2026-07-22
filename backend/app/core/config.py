"""Environment-based application configuration."""

from dataclasses import dataclass
from functools import lru_cache
from os import getenv

from app import __version__

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def _read_boolean(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable safely."""

    raw_value = getenv(name)

    if raw_value is None:
        return default

    return raw_value.strip().lower() in _TRUE_VALUES


def _normalize_api_prefix(value: str) -> str:
    """Normalize an API prefix to a stable slash-prefixed format."""

    normalized = value.strip()

    if not normalized:
        return "/api/v1"

    if not normalized.startswith("/"):
        normalized = f"/{normalized}"

    normalized = normalized.rstrip("/")

    return normalized or "/api/v1"


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable application settings."""

    app_name: str
    app_environment: str
    app_version: str
    api_prefix: str
    debug: bool


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings(
        app_name=getenv("APP_NAME", "Company AI API"),
        app_environment=getenv("APP_ENV", "development"),
        app_version=getenv("APP_VERSION", __version__),
        api_prefix=_normalize_api_prefix(
            getenv("BACKEND_API_PREFIX", "/api/v1")
        ),
        debug=_read_boolean("BACKEND_DEBUG", default=False),
    )
