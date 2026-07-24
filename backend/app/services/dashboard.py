"""Read-only dashboard summary orchestration."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.repositories.dashboard import DashboardRepository
from app.schemas.dashboard import (
    DashboardAuditEvent,
    DashboardCounts,
    DashboardReadinessStatus,
    DashboardServiceStatus,
    DashboardServiceSummary,
    DashboardSummaryResponse,
)

RECENT_AUDIT_EVENT_LIMIT = 5


class DashboardService:
    """Build the safe overview response from one request session."""

    def __init__(
        self,
        *,
        repository: DashboardRepository,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._settings = settings

    def get_summary(self, *, company_id: UUID) -> DashboardSummaryResponse:
        """Return the current company overview without side effects."""

        snapshot = self._repository.get_count_snapshot(
            company_id=company_id
        )
        recent_events = self._repository.list_recent_audit_events(
            company_id=company_id,
            limit=RECENT_AUDIT_EVENT_LIMIT,
        )
        return DashboardSummaryResponse(
            service=DashboardServiceSummary(
                status=DashboardServiceStatus.OK,
                readiness=DashboardReadinessStatus.REACHABLE,
                environment=self._settings.app_environment,
                version=self._settings.app_version,
            ),
            counts=DashboardCounts(
                provider_connections=snapshot.provider_connections,
                enabled_provider_connections=(
                    snapshot.enabled_provider_connections
                ),
                provider_credentials=snapshot.provider_credentials,
                pending_approvals=snapshot.pending_approvals,
                provider_executions=snapshot.provider_executions,
                failed_provider_executions=(
                    snapshot.failed_provider_executions
                ),
                audit_events=snapshot.audit_events,
            ),
            recent_audit_events=[
                DashboardAuditEvent.model_validate(
                    {
                        "id": event.id,
                        "actor_type": event.actor_type,
                        "action": event.action,
                        "resource_type": event.resource_type,
                        "resource_id": event.resource_id,
                        "created_at": event.created_at,
                    }
                )
                for event in recent_events
            ],
        )


def get_dashboard_service(
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DashboardService:
    """Construct a request-scoped dashboard service."""

    return DashboardService(
        repository=DashboardRepository(session),
        settings=settings,
    )
