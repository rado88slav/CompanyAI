"""First-run setup detection and bootstrap safety tests."""

import io

from fastapi.testclient import TestClient

from app.api.routes.first_run import get_db_session
from app.cli.bootstrap_first_run import main
from app.main import app
from app.schemas.first_run import FirstRunInitializeRequest


class FakeScalarSession:
    def __init__(self, values: list[int]) -> None:
        self.values = values

    def scalar(self, _statement):
        return self.values.pop(0)


def test_first_run_status_reports_setup_required_without_secrets():
    app.dependency_overrides[get_db_session] = lambda: FakeScalarSession([0, 0])
    try:
        response = TestClient(app).get("/api/v1/first-run/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "initialized": False,
        "setup_required": True,
        "administrator_count": 0,
        "company_count": 0,
        "bootstrap_method": "local_wizard",
    }
    assert "token" not in str(body).lower()
    assert "password" not in str(body).lower()


def test_first_run_openapi_route_is_registered():
    assert "/api/v1/first-run/status" in app.openapi()["paths"]
    assert "/api/v1/first-run/initialize" in app.openapi()["paths"]


def test_first_run_bootstrap_input_requires_strong_password(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(
            "\n".join(
                [
                    "HVAC Company",
                    "hvac-company",
                    "owner@example.test",
                    "Owner User",
                    "weak-password",
                    "en",
                    "Europe/Sofia",
                ]
            )
        ),
    )

    assert main() == 2
    captured = capsys.readouterr()
    assert "Invalid first-run setup data" in captured.err
    assert "weak-password" not in captured.err


def test_first_run_bootstrap_input_accepts_valid_payload():
    item = FirstRunInitializeRequest(
        company_name="HVAC Company",
        company_slug="hvac-company",
        administrator_email="OWNER@example.test",
        administrator_full_name="Owner User",
        administrator_password="Str0ng-local-setup!",
        language="en",
        timezone="Europe/Sofia",
    )

    assert item.company_slug == "hvac-company"
    assert item.administrator_email == "owner@example.test"
    assert item.language == "en"


def test_first_run_initialize_request_rejects_weak_password():
    try:
        FirstRunInitializeRequest(
            company_name="HVAC Company",
            company_slug="hvac-company",
            administrator_email="owner@example.test",
            administrator_full_name="Owner User",
            administrator_password="weak-password",
            language="en",
            timezone="Europe/Sofia",
        )
    except Exception as exc:
        assert "password" in str(exc).lower()
    else:
        raise AssertionError("Weak first-run password was accepted.")
