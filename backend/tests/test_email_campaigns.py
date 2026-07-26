"""Tests for deterministic read-only mock email campaigns."""

from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies.authentication import require_current_administrator
from app.api.dependencies.company_authorization import require_emails_read
from app.core.provider_connections import provider_registry
from app.main import app
from app.schemas.company_context import ActiveCompanyContext
from app.services.email_campaign import MockEmailCampaignService


def context(company_id):
    return ActiveCompanyContext(
        administrator=SimpleNamespace(id=uuid4(), is_superuser=False),
        company=SimpleNamespace(id=company_id, status="active", is_active=True),
        membership=SimpleNamespace(role="admin", status="active"),
        is_platform_superuser=False,
    )


def test_mock_email_provider_descriptor_is_read_only_and_credentialless() -> None:
    descriptor = provider_registry.require("local_mock_email")
    assert descriptor.authentication_type == "none"
    assert descriptor.required_secret_fields == frozenset()
    assert descriptor.optional_secret_fields == frozenset()
    assert descriptor.capabilities == frozenset({"email.campaign.read"})


def test_mock_campaigns_are_deterministic_and_company_scoped() -> None:
    service = MockEmailCampaignService()
    company_id = uuid4()
    first, total = service.list_campaigns(company_id=company_id, limit=50, offset=0)
    second, second_total = service.list_campaigns(company_id=company_id, limit=50, offset=0)
    other, _ = service.list_campaigns(company_id=uuid4(), limit=50, offset=0)

    assert total == second_total == 2
    assert [item.id for item in first] == [item.id for item in second]
    assert [item.id for item in first] != [item.id for item in other]
    assert {item.provider_key for item in first} == {"local_mock_email"}
    assert all(item.sent_count <= item.audience_count for item in first)


def test_mock_campaign_api_uses_company_context_and_safe_schema() -> None:
    company_id = uuid4()
    app.dependency_overrides[require_current_administrator] = lambda: SimpleNamespace(id=uuid4(), is_superuser=False)
    app.dependency_overrides[require_emails_read] = lambda: context(company_id)
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/companies/{company_id}/email-campaigns",
                headers={"Authorization": "Bearer test", "X-Company-ID": str(company_id)},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["items"][0]["company_id"] == str(company_id)
    assert "secret" not in str(body).lower()
    assert "token" not in str(body).lower()


def test_mock_campaign_openapi_routes_are_registered() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/companies/{company_id}/email-campaigns" in paths
    assert "/api/v1/companies/{company_id}/agent-runtime/tools/email-campaigns/setup" in paths
