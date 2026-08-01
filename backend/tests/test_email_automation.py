"""Email automation settings and dry-run planner tests."""

from datetime import UTC, datetime
from random import Random
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.models.provider_connection import ProviderConnection
from app.schemas.email_campaign import (
    CampaignLimitSettings,
    CampaignSchedulePreviewRequest,
    CampaignScheduleSettings,
    MailboxRotationSettings,
    PauseReason,
    RandomizedTimingSettings,
    SendWindow,
)
from app.services.email_automation import EmailAutomationService, EmailAutomationValidationError
from app.services.generic_smtp_imap import GENERIC_MAILBOX_HEALTH_KEY


class FakeSettings:
    def __init__(self) -> None:
        self.value: dict[str, object] | None = None

    def get(self, *, company_id: UUID, category: str, key: str):
        if self.value is None:
            return None
        return SimpleNamespace(value=self.value)

    def create(self, *, company_id: UUID, category: str, key: str, setting_data):
        self.value = setting_data.value
        return SimpleNamespace(value=self.value)

    def replace_value(self, setting, setting_data):
        self.value = setting_data.value
        return SimpleNamespace(value=self.value)


class FakeProviderConnections:
    def __init__(self, connections: list[ProviderConnection], credentials: dict[UUID, object] | None = None) -> None:
        self.connections = connections
        self.credentials = credentials or {}

    def count_connections(self, *, company_id: UUID) -> int:
        return len([item for item in self.connections if item.company_id == company_id])

    def list_connections(self, *, company_id: UUID, limit: int, offset: int) -> list[ProviderConnection]:
        return [item for item in self.connections if item.company_id == company_id][offset: offset + limit]

    def active_credential(self, *, company_id: UUID, connection_id: UUID, for_update: bool = False):
        return self.credentials.get(connection_id)


class FakeAudit:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def append_company_event(self, **kwargs):
        self.events.append(kwargs)
        return SimpleNamespace(id=uuid4())


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def mailbox(company_id: UUID, *, status: str = "active") -> ProviderConnection:
    return ProviderConnection(
        id=uuid4(),
        company_id=company_id,
        provider_key="generic_smtp_imap",
        display_name="Primary mailbox",
        slug=f"mailbox-{uuid4()}",
        authentication_type="username_password",
        status=status,
        configuration={"email_address": "mailbox@example.test"},
        metadata_={
            GENERIC_MAILBOX_HEALTH_KEY: {
                "smtp": {"status": "succeeded"},
                "imap": {"status": "succeeded"},
            }
        },
    )


def service(
    *,
    settings: FakeSettings | None = None,
    providers: FakeProviderConnections | None = None,
    audit: FakeAudit | None = None,
    session: FakeSession | None = None,
) -> EmailAutomationService:
    return EmailAutomationService(
        settings=settings or FakeSettings(),
        provider_connections=providers or FakeProviderConnections([]),
        audit=audit or FakeAudit(),
        session=session or FakeSession(),
        clock=lambda: datetime(2026, 8, 3, 7, 30, tzinfo=UTC),
        random_source=Random(7),
    )


def test_schedule_schema_rejects_overlapping_windows_and_bad_timezone() -> None:
    with pytest.raises(ValidationError):
        CampaignScheduleSettings(timezone="Not/AZone")
    with pytest.raises(ValidationError):
        CampaignScheduleSettings(send_windows=[SendWindow(start="09:00", end="12:00"), SendWindow(start="11:00", end="13:00")])
    with pytest.raises(ValidationError):
        CampaignScheduleSettings(
            randomized_timing=RandomizedTimingSettings(minimum_delay_minutes=60, maximum_delay_minutes=10),
        )
    with pytest.raises(ValidationError):
        CampaignScheduleSettings(limits=CampaignLimitSettings(campaign_hourly=50, campaign_daily=20))
    with pytest.raises(ValidationError):
        CampaignScheduleSettings(worker_enabled=True)


def test_preview_returns_planned_slots_for_active_healthy_mailboxes() -> None:
    company_id = uuid4()
    item = mailbox(company_id)
    settings = FakeSettings()
    settings.value = CampaignScheduleSettings(
        randomized_timing=RandomizedTimingSettings(minimum_delay_minutes=1, maximum_delay_minutes=1, jitter_minutes=0),
        limits=CampaignLimitSettings(campaign_hourly=5, campaign_daily=5, mailbox_hourly=5, mailbox_daily=5),
        mailbox_rotation=MailboxRotationSettings(allowed_connection_ids=[item.id]),
    ).model_dump(mode="json")
    result = service(settings=settings, providers=FakeProviderConnections([item], {item.id: SimpleNamespace(expires_at=None)})).preview(
        company_id=company_id,
        request=CampaignSchedulePreviewRequest(recipient_count=3, include_follow_ups=False),
        actor=SimpleNamespace(id=uuid4()),
    )

    assert [slot.status for slot in result.slots] == ["planned", "planned", "planned"]
    assert {slot.mailbox_connection_id for slot in result.slots} == {item.id}
    assert result.worker_enabled is False
    assert result.worker_contract["preview_only"] is True


def test_preview_skips_when_no_suitable_mailbox_exists() -> None:
    company_id = uuid4()
    result = service().preview(
        company_id=company_id,
        request=CampaignSchedulePreviewRequest(recipient_count=2),
        actor=SimpleNamespace(id=uuid4()),
    )

    assert result.slots == []
    assert result.skipped[0].reason == PauseReason.NO_SUITABLE_MAILBOX.value


def test_save_rejects_cross_company_mailbox_reference() -> None:
    company_id = uuid4()
    other_company_id = uuid4()
    other_mailbox = mailbox(other_company_id)

    with pytest.raises(EmailAutomationValidationError):
        service(providers=FakeProviderConnections([other_mailbox])).save_settings(
            company_id=company_id,
            data=CampaignScheduleSettings(mailbox_rotation=MailboxRotationSettings(allowed_connection_ids=[other_mailbox.id])),
            actor=SimpleNamespace(id=uuid4()),
        )


def test_save_pause_resume_persist_settings_and_audit_events() -> None:
    company_id = uuid4()
    settings = FakeSettings()
    audit = FakeAudit()
    session = FakeSession()
    svc = service(settings=settings, audit=audit, session=session)
    actor = SimpleNamespace(id=uuid4())

    saved = svc.save_settings(company_id=company_id, data=CampaignScheduleSettings(status="scheduled"), actor=actor)
    paused = svc.pause(company_id=company_id, reason=PauseReason.MANUAL, actor=actor)
    resumed = svc.resume(company_id=company_id, actor=actor)

    assert saved.status == "scheduled"
    assert paused.status == "paused"
    assert resumed.status == "scheduled"
    assert session.commits == 3
    assert [event["action"] for event in audit.events] == [
        "email_automation.settings_updated",
        "email_automation.paused",
        "email_automation.resumed",
    ]
