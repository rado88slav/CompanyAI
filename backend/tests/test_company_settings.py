"""Tests for company-owned setting API behavior."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.dependencies.authentication import (
    require_current_administrator,
)
from app.api.dependencies.company_context import (
    require_matching_active_company,
)

from app.main import app
from app.schemas.company_setting import CompanySettingUpsert
from app.services.company import CompanyNotFoundError
from app.services.company_setting import (
    CompanySettingNotFoundError,
    get_company_setting_service,
)

NOW = datetime.now(timezone.utc)


class FakeCompanySetting:
    """Object compatible with CompanySettingResponse validation."""

    def __init__(
        self,
        *,
        setting_id: UUID,
        company_id: UUID,
        category: str,
        key: str,
        value: Any,
    ) -> None:
        self.id = setting_id
        self.company_id = company_id
        self.category = category
        self.key = key
        self.value = value
        self.created_at = NOW
        self.updated_at = NOW


class FakeCompanySettingService:
    """In-memory service used by CompanySetting API tests."""

    def __init__(
        self,
        company_ids: set[UUID],
    ) -> None:
        self.company_ids = company_ids
        self.settings: dict[
            tuple[UUID, str, str],
            FakeCompanySetting,
        ] = {}

    def _require_company(
        self,
        company_id: UUID,
    ) -> None:
        """Reject operations for an unknown company."""

        if company_id not in self.company_ids:
            raise CompanyNotFoundError

    def upsert_setting(
        self,
        *,
        company_id: UUID,
        category: str,
        key: str,
        setting_data: CompanySettingUpsert,
    ) -> FakeCompanySetting:
        """Create or replace one in-memory setting."""

        self._require_company(company_id)

        identity = (
            company_id,
            category,
            key,
        )

        setting = self.settings.get(identity)

        if setting is None:
            setting = FakeCompanySetting(
                setting_id=uuid4(),
                company_id=company_id,
                category=category,
                key=key,
                value=setting_data.value,
            )

            self.settings[identity] = setting
        else:
            setting.value = setting_data.value
            setting.updated_at = datetime.now(timezone.utc)

        return setting

    def get_setting(
        self,
        *,
        company_id: UUID,
        category: str,
        key: str,
    ) -> FakeCompanySetting:
        """Return one in-memory setting."""

        self._require_company(company_id)

        setting = self.settings.get(
            (
                company_id,
                category,
                key,
            )
        )

        if setting is None:
            raise CompanySettingNotFoundError

        return setting

    def list_settings(
        self,
        *,
        company_id: UUID,
        category: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[FakeCompanySetting], int]:
        """Return one page of sorted in-memory settings."""

        self._require_company(company_id)

        matching_settings = [
            setting
            for setting in self.settings.values()
            if setting.company_id == company_id
            and (
                category is None
                or setting.category == category
            )
        ]

        matching_settings.sort(
            key=lambda setting: (
                setting.category,
                setting.key,
                str(setting.id),
            )
        )

        return (
            matching_settings[offset:offset + limit],
            len(matching_settings),
        )

    def delete_setting(
        self,
        *,
        company_id: UUID,
        category: str,
        key: str,
    ) -> None:
        """Delete one in-memory setting."""

        setting = self.get_setting(
            company_id=company_id,
            category=category,
            key=key,
        )

        del self.settings[
            (
                setting.company_id,
                setting.category,
                setting.key,
            )
        ]


def create_client(
    service: FakeCompanySettingService,
) -> TestClient:
    """Create a client with the setting service overridden."""

    # Authentication behavior is tested separately.
    app.dependency_overrides[
        require_current_administrator
    ] = lambda: object()

    app.dependency_overrides[
        require_matching_active_company
    ] = lambda: object()

    app.dependency_overrides[
        get_company_setting_service
    ] = lambda: service

    return TestClient(app)


def test_upsert_and_get_company_setting() -> None:
    company_id = uuid4()

    service = FakeCompanySettingService(
        company_ids={company_id},
    )

    try:
        with create_client(service) as client:
            upsert_response = client.put(
                (
                    f"/api/v1/companies/{company_id}"
                    "/settings/general/timezone"
                ),
                json={
                    "value": "Europe/Sofia",
                },
            )

            get_response = client.get(
                (
                    f"/api/v1/companies/{company_id}"
                    "/settings/general/timezone"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert upsert_response.status_code == 200
    assert get_response.status_code == 200
    assert get_response.json()["company_id"] == str(
        company_id
    )
    assert get_response.json()["category"] == "general"
    assert get_response.json()["key"] == "timezone"
    assert get_response.json()["value"] == "Europe/Sofia"


def test_upsert_replaces_existing_setting_value() -> None:
    company_id = uuid4()

    service = FakeCompanySettingService(
        company_ids={company_id},
    )

    try:
        with create_client(service) as client:
            first_response = client.put(
                (
                    f"/api/v1/companies/{company_id}"
                    "/settings/ai/model"
                ),
                json={
                    "value": "first-model",
                },
            )

            second_response = client.put(
                (
                    f"/api/v1/companies/{company_id}"
                    "/settings/ai/model"
                ),
                json={
                    "value": "second-model",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["id"] == (
        second_response.json()["id"]
    )
    assert second_response.json()["value"] == (
        "second-model"
    )
    assert len(service.settings) == 1


def test_list_company_settings_with_category_filter() -> None:
    company_id = uuid4()

    service = FakeCompanySettingService(
        company_ids={company_id},
    )

    service.upsert_setting(
        company_id=company_id,
        category="general",
        key="timezone",
        setting_data=CompanySettingUpsert(
            value="Europe/Sofia",
        ),
    )

    service.upsert_setting(
        company_id=company_id,
        category="email",
        key="provider",
        setting_data=CompanySettingUpsert(
            value="test-provider",
        ),
    )

    service.upsert_setting(
        company_id=company_id,
        category="email",
        key="daily-limit",
        setting_data=CompanySettingUpsert(
            value=50,
        ),
    )

    try:
        with create_client(service) as client:
            response = client.get(
                (
                    f"/api/v1/companies/{company_id}/settings"
                    "?category=email&limit=1&offset=1"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["limit"] == 1
    assert response.json()["offset"] == 1
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["category"] == (
        "email"
    )


def test_settings_are_isolated_between_companies() -> None:
    first_company_id = uuid4()
    second_company_id = uuid4()

    service = FakeCompanySettingService(
        company_ids={
            first_company_id,
            second_company_id,
        },
    )

    service.upsert_setting(
        company_id=first_company_id,
        category="general",
        key="timezone",
        setting_data=CompanySettingUpsert(
            value="Europe/Sofia",
        ),
    )

    service.upsert_setting(
        company_id=second_company_id,
        category="general",
        key="timezone",
        setting_data=CompanySettingUpsert(
            value="Europe/Bucharest",
        ),
    )

    try:
        with create_client(service) as client:
            response = client.get(
                (
                    f"/api/v1/companies/{first_company_id}"
                    "/settings"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["company_id"] == (
        str(first_company_id)
    )
    assert response.json()["items"][0]["value"] == (
        "Europe/Sofia"
    )


def test_delete_company_setting() -> None:
    company_id = uuid4()

    service = FakeCompanySettingService(
        company_ids={company_id},
    )

    service.upsert_setting(
        company_id=company_id,
        category="general",
        key="timezone",
        setting_data=CompanySettingUpsert(
            value="Europe/Sofia",
        ),
    )

    try:
        with create_client(service) as client:
            delete_response = client.delete(
                (
                    f"/api/v1/companies/{company_id}"
                    "/settings/general/timezone"
                )
            )

            get_response = client.get(
                (
                    f"/api/v1/companies/{company_id}"
                    "/settings/general/timezone"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert get_response.status_code == 404
    assert get_response.json() == {
        "detail": "Company setting was not found."
    }


def test_missing_company_setting_returns_not_found() -> None:
    company_id = uuid4()

    service = FakeCompanySettingService(
        company_ids={company_id},
    )

    try:
        with create_client(service) as client:
            response = client.get(
                (
                    f"/api/v1/companies/{company_id}"
                    "/settings/general/missing-setting"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Company setting was not found."
    }


def test_unknown_company_returns_not_found() -> None:
    service = FakeCompanySettingService(
        company_ids=set(),
    )

    try:
        with create_client(service) as client:
            response = client.get(
                (
                    f"/api/v1/companies/{uuid4()}"
                    "/settings"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Company was not found."
    }


def test_invalid_setting_category_is_rejected() -> None:
    company_id = uuid4()

    service = FakeCompanySettingService(
        company_ids={company_id},
    )

    try:
        with create_client(service) as client:
            response = client.put(
                (
                    f"/api/v1/companies/{company_id}"
                    "/settings/Invalid Category/timezone"
                ),
                json={
                    "value": "Europe/Sofia",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
