"""Persistence operations for append-only audit events."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog, AuditScope


class AuditLogRepository:
    """Append and retrieve audit events without owning transactions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        scope: str,
        company_id: UUID | None,
        actor_type: str,
        actor_administrator_id: UUID | None,
        actor_agent_id: UUID | None = None,
        action: str,
        resource_type: str,
        resource_id: UUID | None,
        details: dict[str, Any],
    ) -> AuditLog:
        """Append and flush one audit event without committing."""

        event = AuditLog(
            scope=scope,
            company_id=company_id,
            actor_type=actor_type,
            actor_administrator_id=actor_administrator_id,
            actor_agent_id=actor_agent_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )
        self._session.add(event)
        self._session.flush()
        self._session.refresh(event)
        return event

    def list_for_company(
        self,
        *,
        company_id: UUID,
        limit: int,
        offset: int,
        event_type: str | None = None,
        source: str | None = None,
        severity: str | None = None,
        actor: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[AuditLog]:
        """Return company events in deterministic newest-first order."""

        statement = (
            select(AuditLog)
            .where(
                AuditLog.company_id == company_id,
                AuditLog.scope == AuditScope.COMPANY.value,
            )
        )
        statement = self._activity_filters(
            statement,
            event_type=event_type,
            source=source,
            severity=severity,
            actor=actor,
            date_from=date_from,
            date_to=date_to,
        )
        statement = statement.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).offset(offset)
        return list(self._session.scalars(statement).all())

    def count_for_company(
        self,
        *,
        company_id: UUID,
        event_type: str | None = None,
        source: str | None = None,
        severity: str | None = None,
        actor: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> int:
        """Count company-scoped events for exactly one company."""

        statement = select(func.count()).select_from(AuditLog).where(
            AuditLog.company_id == company_id,
            AuditLog.scope == AuditScope.COMPANY.value,
        )
        statement = self._activity_filters(
            statement,
            event_type=event_type,
            source=source,
            severity=severity,
            actor=actor,
            date_from=date_from,
            date_to=date_to,
        )
        return int(self._session.scalar(statement) or 0)

    @staticmethod
    def _activity_filters(
        statement: object,
        *,
        event_type: str | None,
        source: str | None,
        severity: str | None,
        actor: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ):
        if event_type:
            statement = statement.where(AuditLog.resource_type == event_type)
        if source:
            source_filters = {
                "agent": [AuditLog.action.like("agent%")],
                "approval": [AuditLog.action.like("approval_%"), AuditLog.action.like("authorization.%")],
                "provider": [AuditLog.action.like("provider%")],
                "email": [AuditLog.action.like("email%")],
                "system": [
                    AuditLog.action.like("company%"),
                    AuditLog.action.like("membership%"),
                    AuditLog.action.like("administrator%"),
                ],
            }
            statement = statement.where(or_(*source_filters.get(source, [AuditLog.action.like(f"{source}.%")])))
        if severity == "error":
            statement = statement.where(AuditLog.action.like("%.failed"))
        elif severity == "warning":
            statement = statement.where(
                AuditLog.action.like("%.denied")
                | AuditLog.action.like("%.cancelled")
                | AuditLog.action.like("%.revoked")
            )
        elif severity == "info":
            statement = statement.where(
                ~AuditLog.action.like("%.failed"),
                ~AuditLog.action.like("%.denied"),
                ~AuditLog.action.like("%.cancelled"),
                ~AuditLog.action.like("%.revoked"),
            )
        if actor:
            statement = statement.where(AuditLog.actor_type == actor)
        if date_from:
            statement = statement.where(AuditLog.created_at >= date_from)
        if date_to:
            statement = statement.where(AuditLog.created_at <= date_to)
        return statement
