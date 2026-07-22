"""Environment-based application configuration."""

from dataclasses import dataclass
from functools import lru_cache
from os import getenv

from sqlalchemy import URL

from app import __version__

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def _read_boolean(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable safely."""

    raw_value = getenv(name)

    if raw_value is None:
        return default

    return raw_value.strip().lower() in _TRUE_VALUES


def _read_positive_integer(name: str, default: int) -> int:
    """Read and validate a positive integer environment variable."""

    raw_value = getenv(name)

    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {name} must be an integer."
        ) from exc

    if value <= 0:
        raise ValueError(
            f"Environment variable {name} must be greater than zero."
        )

    return value


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

    postgres_host: str
    postgres_port: int
    postgres_database: str
    postgres_user: str
    postgres_password: str

    database_pool_size: int
    database_max_overflow: int
    database_pool_timeout: int
    database_connect_timeout: int

    @property
    def database_url(self) -> URL:
        """Create a safely encoded SQLAlchemy PostgreSQL URL."""

        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_database,
        )


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
        postgres_host=getenv("POSTGRES_HOST", "postgres"),
        postgres_port=_read_positive_integer(
            "POSTGRES_PORT",
            default=5432,
        ),
        postgres_database=getenv("POSTGRES_DB", "company_ai"),
        postgres_user=getenv("POSTGRES_USER", "company_ai"),
        postgres_password=getenv("POSTGRES_PASSWORD", ""),
        database_pool_size=_read_positive_integer(
            "DATABASE_POOL_SIZE",
            default=5,
        ),
        database_max_overflow=_read_positive_integer(
            "DATABASE_MAX_OVERFLOW",
            default=10,
        ),
        database_pool_timeout=_read_positive_integer(
            "DATABASE_POOL_TIMEOUT",
            default=30,
        ),
        database_connect_timeout=_read_positive_integer(
            "DATABASE_CONNECT_TIMEOUT",
            default=5,
        ),
    )
