"""Real PostgreSQL Alembic upgrade regression tests.

These tests intentionally require an explicit disposable database URL. They
must never infer or use the Local Edition database automatically.
"""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATABASE_URL_ENV = "COMPANYAI_MIGRATION_TEST_DATABASE_URL"


def _config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


def _database_url() -> str:
    value = os.getenv(DATABASE_URL_ENV)
    if not value:
        pytest.skip(f"{DATABASE_URL_ENV} is required for disposable PostgreSQL migration tests.")
    return value


def _version(engine: sa.Engine) -> str:
    with engine.connect() as connection:
        return str(connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one())


def _reset_disposable_schema(engine: sa.Engine) -> None:
    with engine.begin() as connection:
        connection.execute(sa.text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(sa.text("CREATE SCHEMA public"))


def test_postgresql_upgrade_from_0014_to_head_with_varchar_32_version() -> None:
    database_url = _database_url()
    engine = sa.create_engine(database_url)
    config = _config(database_url)
    try:
        _reset_disposable_schema(engine)
        command.upgrade(config, "head")
        assert _version(engine) == "0015_live_execution_outcomes"

        _reset_disposable_schema(engine)
        command.upgrade(config, "0014_email_workflow")
        with engine.connect() as connection:
            row = connection.execute(
                sa.text(
                    """
                    SELECT character_maximum_length
                    FROM information_schema.columns
                    WHERE table_name = 'alembic_version'
                      AND column_name = 'version_num'
                    """
                )
            ).scalar_one()
            assert row == 32
        assert _version(engine) == "0014_email_workflow"

        command.upgrade(config, "head")
        assert _version(engine) == "0015_live_execution_outcomes"

        with engine.connect() as connection:
            status_constraint = connection.execute(
                sa.text(
                    """
                    SELECT pg_get_constraintdef(oid)
                    FROM pg_constraint
                    WHERE conname = 'ck_provider_executions_status'
                    """
                )
            ).scalar_one()
            assert "outcome_uncertain" in status_constraint
            assert "failed_before_send" in status_constraint

        command.downgrade(config, "0014_email_workflow")
        assert _version(engine) == "0014_email_workflow"
        command.upgrade(config, "head")
        assert _version(engine) == "0015_live_execution_outcomes"
    finally:
        _reset_disposable_schema(engine)
        engine.dispose()
