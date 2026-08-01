"""Email automation settings persistence and dry-run schedule planning."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from random import Random
from typing import Annotated, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import Depends
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.administrator import Administrator
from app.models.audit_log import AuditAction
from app.models.provider_connection import ProviderConnection
from app.repositories.audit_log import AuditLogRepository
from app.repositories.company_setting import CompanySettingRepository
from app.repositories.provider_connection import ProviderConnectionRepository
from app.schemas.company_setting import CompanySettingUpsert
from app.schemas.email_campaign import (
    CampaignSchedulePreviewRequest,
    CampaignSchedulePreviewResponse,
    CampaignSchedulePreviewSlot,
    CampaignScheduleSettings,
    MailboxRotationStrategy,
    PauseReason,
)
from app.services.audit_log import AuditLogService
from app.services.generic_smtp_imap import GENERIC_MAILBOX_HEALTH_KEY

EMAIL_AUTOMATION_CATEGORY = "email_automation"
CAMPAIGN_SCHEDULE_KEY = "campaign_schedule"


class Clock(Protocol):
    def __call__(self) -> datetime: ...


class EmailAutomationValidationError(Exception):
    """Schedule settings are invalid for the current company resources."""


@dataclass(frozen=True, slots=True)
class EligibleMailbox:
    id: UUID
    display_name: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _json_settings(settings: CampaignScheduleSettings) -> dict[str, object]:
    return settings.model_dump(mode="json")


def _slot_limits(settings: CampaignScheduleSettings) -> dict[str, int | None]:
    return {
        "campaign_hourly": settings.limits.campaign_hourly,
        "campaign_daily": settings.limits.campaign_daily,
        "mailbox_hourly": settings.limits.mailbox_hourly,
        "mailbox_daily": settings.limits.mailbox_daily,
        "company_daily": settings.limits.company_daily,
    }


class EmailAutomationService:
    """Persist non-secret campaign settings and plan preview-only send slots."""

    def __init__(
        self,
        *,
        settings: CompanySettingRepository,
        provider_connections: ProviderConnectionRepository,
        audit: AuditLogService,
        session: Session,
        clock: Clock = _utc_now,
        random_source: Random | None = None,
    ) -> None:
        self._settings = settings
        self._provider_connections = provider_connections
        self._audit = audit
        self._session = session
        self._clock = clock
        self._random = random_source or Random()

    def get_settings(self, *, company_id: UUID) -> CampaignScheduleSettings:
        setting = self._settings.get(
            company_id=company_id,
            category=EMAIL_AUTOMATION_CATEGORY,
            key=CAMPAIGN_SCHEDULE_KEY,
        )
        if setting is None:
            return CampaignScheduleSettings()
        try:
            return CampaignScheduleSettings.model_validate(setting.value)
        except ValidationError as exc:
            raise EmailAutomationValidationError("Stored email automation settings are invalid.") from exc

    def save_settings(
        self,
        *,
        company_id: UUID,
        data: CampaignScheduleSettings,
        actor: Administrator,
    ) -> CampaignScheduleSettings:
        self._validate_connection_references(company_id=company_id, settings=data)
        try:
            existing = self._settings.get(
                company_id=company_id,
                category=EMAIL_AUTOMATION_CATEGORY,
                key=CAMPAIGN_SCHEDULE_KEY,
            )
            payload = CompanySettingUpsert(value=_json_settings(data))
            if existing is None:
                self._settings.create(
                    company_id=company_id,
                    category=EMAIL_AUTOMATION_CATEGORY,
                    key=CAMPAIGN_SCHEDULE_KEY,
                    setting_data=payload,
                )
            else:
                self._settings.replace_value(existing, payload)
            self._audit.append_company_event(
                company_id=company_id,
                actor_administrator_id=actor.id,
                action=AuditAction.EMAIL_AUTOMATION_SETTINGS_UPDATED.value,
                resource_type="email_automation",
                resource_id=None,
                details={
                    "operation": "schedule_settings_saved",
                    "status": data.status,
                    "dry_run": True,
                    "changed": True,
                },
            )
            self._session.commit()
            return data
        except Exception:
            self._session.rollback()
            raise

    def pause(
        self,
        *,
        company_id: UUID,
        reason: PauseReason,
        actor: Administrator,
    ) -> CampaignScheduleSettings:
        current = self.get_settings(company_id=company_id)
        updated = current.model_copy(update={"status": "paused", "pause_reason": reason})
        return self._save_status(company_id=company_id, data=updated, actor=actor, action=AuditAction.EMAIL_AUTOMATION_PAUSED, operation="schedule_paused")

    def resume(self, *, company_id: UUID, actor: Administrator) -> CampaignScheduleSettings:
        current = self.get_settings(company_id=company_id)
        next_status = "scheduled" if current.status == "paused" else current.status
        updated = current.model_copy(update={"status": next_status, "pause_reason": None})
        return self._save_status(company_id=company_id, data=updated, actor=actor, action=AuditAction.EMAIL_AUTOMATION_RESUMED, operation="schedule_resumed")

    def preview(
        self,
        *,
        company_id: UUID,
        request: CampaignSchedulePreviewRequest,
        actor: Administrator,
    ) -> CampaignSchedulePreviewResponse:
        settings = self.get_settings(company_id=company_id)
        self._validate_connection_references(company_id=company_id, settings=settings)
        mailboxes = self._eligible_mailboxes(company_id=company_id, settings=settings)
        slots, skipped = self._plan(settings=settings, mailboxes=mailboxes, recipient_count=request.recipient_count)
        if request.include_follow_ups and settings.follow_up_steps and slots:
            followups = self._plan_followups(settings=settings, mailboxes=mailboxes, primary_slots=slots, limit=request.recipient_count)
            slots.extend(followups)
            slots.sort(key=lambda item: item.planned_at_utc or datetime.max.replace(tzinfo=UTC))
            for sequence, slot in enumerate(slots, start=1):
                slot.sequence = sequence
        try:
            self._audit.append_company_event(
                company_id=company_id,
                actor_administrator_id=actor.id,
                action=AuditAction.EMAIL_AUTOMATION_PREVIEWED.value,
                resource_type="email_automation",
                resource_id=None,
                details={
                    "operation": "schedule_preview",
                    "status": settings.status,
                    "dry_run": True,
                },
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return CampaignSchedulePreviewResponse(
            settings=settings,
            slots=slots,
            skipped=skipped,
            worker_enabled=False,
            worker_contract={
                "worker_enabled": False,
                "persistence": "company_settings",
                "execution": "not_implemented",
                "preview_only": True,
            },
        )

    def _save_status(
        self,
        *,
        company_id: UUID,
        data: CampaignScheduleSettings,
        actor: Administrator,
        action: AuditAction,
        operation: str,
    ) -> CampaignScheduleSettings:
        try:
            existing = self._settings.get(company_id=company_id, category=EMAIL_AUTOMATION_CATEGORY, key=CAMPAIGN_SCHEDULE_KEY)
            payload = CompanySettingUpsert(value=_json_settings(data))
            if existing is None:
                self._settings.create(company_id=company_id, category=EMAIL_AUTOMATION_CATEGORY, key=CAMPAIGN_SCHEDULE_KEY, setting_data=payload)
            else:
                self._settings.replace_value(existing, payload)
            self._audit.append_company_event(
                company_id=company_id,
                actor_administrator_id=actor.id,
                action=action.value,
                resource_type="email_automation",
                resource_id=None,
                details={"operation": operation, "status": data.status, "dry_run": True},
            )
            self._session.commit()
            return data
        except Exception:
            self._session.rollback()
            raise

    def _company_connections(self, company_id: UUID) -> list[ProviderConnection]:
        total = self._provider_connections.count_connections(company_id=company_id)
        return self._provider_connections.list_connections(company_id=company_id, limit=max(total, 1), offset=0)

    def _validate_connection_references(self, *, company_id: UUID, settings: CampaignScheduleSettings) -> None:
        known = {item.id for item in self._company_connections(company_id)}
        referenced = set(settings.mailbox_rotation.allowed_connection_ids)
        referenced.update(settings.mailbox_rotation.paused_connection_ids)
        if settings.mailbox_rotation.preferred_connection_id is not None:
            referenced.add(settings.mailbox_rotation.preferred_connection_id)
        missing = referenced - known
        if missing:
            raise EmailAutomationValidationError("Schedule references provider connections outside this company.")

    def _eligible_mailboxes(self, *, company_id: UUID, settings: CampaignScheduleSettings) -> list[EligibleMailbox]:
        allowed = set(settings.mailbox_rotation.allowed_connection_ids)
        paused = set(settings.mailbox_rotation.paused_connection_ids)
        mailboxes: list[EligibleMailbox] = []
        now = self._clock()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        for item in self._company_connections(company_id):
            if allowed and item.id not in allowed:
                continue
            if item.id in paused or item.provider_key != "generic_smtp_imap" or item.status != "active":
                continue
            credential = self._provider_connections.active_credential(company_id=company_id, connection_id=item.id)
            if credential is None or (credential.expires_at is not None and credential.expires_at <= now):
                continue
            health = item.metadata_.get(GENERIC_MAILBOX_HEALTH_KEY)
            if not isinstance(health, dict):
                continue
            smtp = health.get("smtp")
            imap = health.get("imap")
            if not isinstance(smtp, dict) or smtp.get("status") != "succeeded":
                continue
            if settings.mailbox_rotation.reply_monitoring_required and (not isinstance(imap, dict) or imap.get("status") != "succeeded"):
                continue
            mailboxes.append(EligibleMailbox(id=item.id, display_name=item.display_name))
        return mailboxes

    def _plan(self, *, settings: CampaignScheduleSettings, mailboxes: list[EligibleMailbox], recipient_count: int) -> tuple[list[CampaignSchedulePreviewSlot], list[CampaignSchedulePreviewSlot]]:
        if settings.status == "paused":
            return [], [self._skipped(settings, "paused", settings.pause_reason.value if settings.pause_reason else "manual")]
        if not mailboxes:
            return [], [self._skipped(settings, "skipped", PauseReason.NO_SUITABLE_MAILBOX.value)]
        zone = ZoneInfo(settings.timezone)
        cursor = self._start_cursor(settings, zone)
        slots: list[CampaignSchedulePreviewSlot] = []
        counts: dict[str, int] = {}
        last_mailbox: UUID | None = None
        consecutive = 0
        attempts = 0
        while len(slots) < recipient_count and attempts < recipient_count * 60:
            attempts += 1
            next_time = self._next_allowed_local(cursor, settings, zone)
            if next_time is None:
                break
            mailbox = self._select_mailbox(settings, mailboxes, len(slots), last_mailbox, consecutive)
            if last_mailbox == mailbox.id:
                consecutive += 1
            else:
                last_mailbox, consecutive = mailbox.id, 1
            if self._would_exceed_limits(next_time, mailbox.id, settings, counts):
                cursor = self._bump_after_limit(next_time)
                continue
            self._record_counts(next_time, mailbox.id, counts)
            slots.append(self._slot(settings, len(slots) + 1, next_time, mailbox, "initial"))
            delay = self._random.randint(settings.randomized_timing.minimum_delay_minutes, settings.randomized_timing.maximum_delay_minutes)
            if settings.randomized_timing.jitter_minutes:
                delay += self._random.randint(0, settings.randomized_timing.jitter_minutes)
            cursor = next_time + timedelta(minutes=delay)
        skipped: list[CampaignSchedulePreviewSlot] = []
        if len(slots) < recipient_count:
            skipped.append(self._skipped(settings, "skipped", "outside_schedule_boundaries"))
        return slots, skipped

    def _plan_followups(
        self,
        *,
        settings: CampaignScheduleSettings,
        mailboxes: list[EligibleMailbox],
        primary_slots: list[CampaignSchedulePreviewSlot],
        limit: int,
    ) -> list[CampaignSchedulePreviewSlot]:
        if not mailboxes:
            return []
        zone = ZoneInfo(settings.timezone)
        result: list[CampaignSchedulePreviewSlot] = []
        for primary in primary_slots[:limit]:
            if primary.planned_at_utc is None:
                continue
            base = primary.planned_at_utc.astimezone(zone)
            for step in settings.follow_up_steps[: settings.maximum_follow_ups]:
                local = self._add_followup_delay(base, step.delay_amount, step.delay_unit)
                local = self._next_allowed_local(local, settings, zone)
                if local is None:
                    continue
                mailbox = mailboxes[0]
                result.append(self._slot(settings, len(primary_slots) + len(result) + 1, local, mailbox, f"follow_up_{step.step_number}"))
                break
        return result

    def _add_followup_delay(self, base: datetime, amount: int, unit: str) -> datetime:
        current = base
        if unit == "calendar_days":
            return current + timedelta(days=amount)
        remaining = amount
        while remaining:
            current += timedelta(days=1)
            if current.weekday() < 5:
                remaining -= 1
        return current

    def _start_cursor(self, settings: CampaignScheduleSettings, zone: ZoneInfo) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        cursor = now.astimezone(zone)
        if settings.start_date is not None:
            start = datetime.combine(settings.start_date, time.min, tzinfo=zone)
            if start > cursor:
                cursor = start
        return cursor

    def _next_allowed_local(self, candidate: datetime, settings: CampaignScheduleSettings, zone: ZoneInfo) -> datetime | None:
        current = candidate.astimezone(zone)
        for _ in range(400):
            if settings.end_date is not None and current.date() > settings.end_date:
                return None
            if settings.start_date is not None and current.date() < settings.start_date:
                current = datetime.combine(settings.start_date, time.min, tzinfo=zone)
                continue
            if current.weekday() not in settings.allowed_weekdays:
                current = datetime.combine(current.date() + timedelta(days=1), time.min, tzinfo=zone)
                continue
            for window in settings.send_windows:
                start = datetime.combine(current.date(), window.start, tzinfo=zone)
                end = datetime.combine(current.date(), window.end, tzinfo=zone)
                if current <= start:
                    return start
                if start < current < end:
                    return current
            current = datetime.combine(current.date() + timedelta(days=1), time.min, tzinfo=zone)
        return None

    def _select_mailbox(
        self,
        settings: CampaignScheduleSettings,
        mailboxes: list[EligibleMailbox],
        sequence: int,
        last_mailbox: UUID | None,
        consecutive: int,
    ) -> EligibleMailbox:
        if settings.mailbox_rotation.strategy is MailboxRotationStrategy.RANDOM:
            return mailboxes[self._random.randrange(len(mailboxes))]
        preferred = settings.mailbox_rotation.preferred_connection_id
        if settings.mailbox_rotation.strategy is MailboxRotationStrategy.PREFERRED_WITH_FALLBACK and preferred is not None:
            for mailbox in mailboxes:
                if mailbox.id == preferred and (last_mailbox != mailbox.id or consecutive < settings.limits.mailbox_max_consecutive):
                    return mailbox
        ordered = mailboxes[sequence % len(mailboxes) :] + mailboxes[: sequence % len(mailboxes)]
        for mailbox in ordered:
            if last_mailbox != mailbox.id or consecutive < settings.limits.mailbox_max_consecutive:
                return mailbox
        return ordered[0]

    def _would_exceed_limits(self, local: datetime, mailbox_id: UUID, settings: CampaignScheduleSettings, counts: dict[str, int]) -> bool:
        limit_keys = {
            f"campaign-hour-{local:%Y%m%d%H}": settings.limits.campaign_hourly,
            f"campaign-day-{local:%Y%m%d}": settings.limits.campaign_daily,
            f"mailbox-{mailbox_id}-hour-{local:%Y%m%d%H}": settings.limits.mailbox_hourly,
            f"mailbox-{mailbox_id}-day-{local:%Y%m%d}": settings.limits.mailbox_daily,
        }
        if settings.limits.company_daily is not None:
            limit_keys[f"company-day-{local:%Y%m%d}"] = settings.limits.company_daily
        return any(counts.get(key, 0) >= limit for key, limit in limit_keys.items())

    def _record_counts(self, local: datetime, mailbox_id: UUID, counts: dict[str, int]) -> None:
        for key in (
            f"campaign-hour-{local:%Y%m%d%H}",
            f"campaign-day-{local:%Y%m%d}",
            f"mailbox-{mailbox_id}-hour-{local:%Y%m%d%H}",
            f"mailbox-{mailbox_id}-day-{local:%Y%m%d}",
            f"company-day-{local:%Y%m%d}",
        ):
            counts[key] = counts.get(key, 0) + 1

    def _bump_after_limit(self, local: datetime) -> datetime:
        return (local + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

    def _slot(
        self,
        settings: CampaignScheduleSettings,
        sequence: int,
        planned_at: datetime,
        mailbox: EligibleMailbox,
        recipient_step: str,
    ) -> CampaignSchedulePreviewSlot:
        return CampaignSchedulePreviewSlot(
            sequence=sequence,
            planned_at_utc=planned_at.astimezone(UTC),
            planned_at_local=planned_at.isoformat(),
            timezone=settings.timezone,
            mailbox_connection_id=mailbox.id,
            mailbox_display_name=mailbox.display_name,
            campaign_key=settings.campaign_key,
            recipient_step=recipient_step,
            status="planned",
            reason=None,
            applicable_limits=_slot_limits(settings),
        )

    def _skipped(self, settings: CampaignScheduleSettings, status: str, reason: str) -> CampaignSchedulePreviewSlot:
        return CampaignSchedulePreviewSlot(
            sequence=1,
            planned_at_utc=None,
            planned_at_local=None,
            timezone=settings.timezone,
            mailbox_connection_id=None,
            mailbox_display_name=None,
            campaign_key=settings.campaign_key,
            recipient_step="initial",
            status=status,
            reason=reason,
            applicable_limits=_slot_limits(settings),
        )


def get_email_automation_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> EmailAutomationService:
    return EmailAutomationService(
        settings=CompanySettingRepository(session),
        provider_connections=ProviderConnectionRepository(session),
        audit=AuditLogService(AuditLogRepository(session)),
        session=session,
    )
