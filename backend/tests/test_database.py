"""Tests for backend database readiness."""

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db_session
from app.main import app


class HealthyDatabaseSession:
    """Minimal successful database session test double."""

    def execute(self, statement: object) -> None:
        del statement


class UnavailableDatabaseSession:
    """Minimal failed database session test double."""

    def execute(self, statement: object) -> None:
        del statement
        raise SQLAlchemyError("Database unavailable")


def override_healthy_database_session(
) -> Generator[HealthyDatabaseSession, None, None]:
    """Provide a successful database session test double."""

    yield HealthyDatabaseSession()


def override_unavailable_database_session(
) -> Generator[UnavailableDatabaseSession, None, None]:
    """Provide an unavailable database session test double."""

    yield UnavailableDatabaseSession()


def test_database_readiness_endpoint() -> None:
    app.dependency_overrides[get_db_session] = (
        override_healthy_database_session
    )

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "backend",
        "database": "reachable",
    }


def test_database_readiness_endpoint_returns_503() -> None:
    app.dependency_overrides[get_db_session] = (
        override_unavailable_database_session
    )

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Database is unavailable.",
    }
