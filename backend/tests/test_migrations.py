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

    assert script_directory.get_heads() == ["0001_initial"]


def test_initial_migration_is_available() -> None:
    """The initial migration must be discoverable by Alembic."""

    script_directory = ScriptDirectory.from_config(
        create_alembic_config()
    )

    revision = script_directory.get_revision("0001_initial")

    assert revision is not None
    assert revision.down_revision is None
