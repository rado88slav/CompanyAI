"""Tests for the initial backend endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint() -> None:
    response = client.get("/")

    assert response.status_code == 200

    body = response.json()

    assert body["service"] == "Company AI API"
    assert body["environment"] == "development"
    assert body["version"] == "0.1.0"
    assert body["documentation"] == "/docs"


def test_health_endpoint() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "backend",
        "environment": "development",
        "version": "0.1.0",
    }
