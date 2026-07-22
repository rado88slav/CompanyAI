"""Persistence operations for append-only audit events."""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
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
    ) -> list[AuditLog]:
        """Return company events in deterministic newest-first order."""

        statement = (
            select(AuditLog)
            .where(
                AuditLog.company_id == company_id,
                AuditLog.scope == AuditScope.COMPANY.value,
            )
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.scalars(statement).all())

    def count_for_company(self, *, company_id: UUID) -> int:
        """Count company-scoped events for exactly one company."""

        statement = select(func.count()).select_from(AuditLog).where(
            AuditLog.company_id == company_id,
            AuditLog.scope == AuditScope.COMPANY.value,
        )
        return int(self._session.scalar(statement) or 0)
