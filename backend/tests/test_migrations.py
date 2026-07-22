"""Tests for the Alembic migration configuration."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def create_alembic_config() -> Config:
    """Create an Alembic configuration for file-based validation."""

    return Config(str(BACKEND_ROOT / "alembic.ini"))


def test_migration_history_has_one_head() -> None:
    """The migration graph must never contain multiple heads."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )

    assert script_directory.get_heads() == [
        "0004_administrators"
    ]


def test_initial_migration_is_available() -> None:
    """The initial migration must remain discoverable."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )

    revision = script_directory.get_revision(
        "0001_initial"
    )

    assert revision is not None
    assert revision.down_revision is None


def test_company_migration_follows_initial_revision() -> None:
    """The Company migration must follow the baseline."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )

    revision = script_directory.get_revision(
        "0002_companies"
    )

    assert revision is not None
    assert revision.down_revision == "0001_initial"


def test_company_settings_migration_follows_company_revision() -> None:
    """Company settings must follow the Company migration."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )

    revision = script_directory.get_revision(
        "0003_company_settings"
    )

    assert revision is not None
    assert revision.down_revision == "0002_companies"


def test_administrator_migration_follows_settings_revision() -> None:
    """Administrator storage must follow company settings."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )

    revision = script_directory.get_revision(
        "0004_administrators"
    )

    assert revision is not None
    assert revision.down_revision == "0003_company_settings"
