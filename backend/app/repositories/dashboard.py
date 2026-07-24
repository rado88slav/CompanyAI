"""Read-only company dashboard persistence queries."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.approval import ApprovalRequest, ApprovalRequestStatus
from app.models.audit_log import AuditLog, AuditScope
from app.models.provider_connection import (
    ProviderConnection,
    ProviderConnectionStatus,
    ProviderCredential,
)
from app.models.provider_execution import ProviderExecution


@dataclass(frozen=True, slots=True)
class DashboardCountSnapshot:
    """Immutable aggregate result from one database statement."""

    provider_connections: int
    enabled_provider_connections: int
    provider_credentials: int
    pending_approvals: int
    provider_executions: int
    failed_provider_executions: int
    audit_events: int


class DashboardRepository:
    """Retrieve bounded dashboard data without mutations."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_count_snapshot(
        self,
        *,
        company_id: UUID,
    ) -> DashboardCountSnapshot:
        """Return all overview counts from one aggregate statement."""

        def count_for(model: type[object], *criteria: object) -> object:
            return (
                select(func.count())
                .select_from(model)
                .where(*criteria)
                .scalar_subquery()
            )

        statement = select(
            count_for(
                ProviderConnection,
                ProviderConnection.company_id == company_id,
            ).label("provider_connections"),
            count_for(
                ProviderConnection,
                ProviderConnection.company_id == company_id,
                ProviderConnection.status
                == ProviderConnectionStatus.ACTIVE.value,
            ).label("enabled_provider_connections"),
            count_for(
                ProviderCredential,
                ProviderCredential.company_id == company_id,
            ).label("provider_credentials"),
            count_for(
                ApprovalRequest,
                ApprovalRequest.company_id == company_id,
                ApprovalRequest.status == ApprovalRequestStatus.PENDING.value,
            ).label("pending_approvals"),
            count_for(
                ProviderExecution,
                ProviderExecution.company_id == company_id,
            ).label("provider_executions"),
            count_for(
                ProviderExecution,
                ProviderExecution.company_id == company_id,
                ProviderExecution.status == "failed",
            ).label("failed_provider_executions"),
            count_for(
                AuditLog,
                AuditLog.company_id == company_id,
                AuditLog.scope == AuditScope.COMPANY.value,
            ).label("audit_events"),
        )
        row = self._session.execute(statement).one()
        return DashboardCountSnapshot(
            provider_connections=int(row.provider_connections),
            enabled_provider_connections=int(
                row.enabled_provider_connections
            ),
            provider_credentials=int(row.provider_credentials),
            pending_approvals=int(row.pending_approvals),
            provider_executions=int(row.provider_executions),
            failed_provider_executions=int(
                row.failed_provider_executions
            ),
            audit_events=int(row.audit_events),
        )

    def list_recent_audit_events(
        self,
        *,
        company_id: UUID,
        limit: int,
    ) -> list[AuditLog]:
        """Return a deterministic bounded company activity window."""

        statement = (
            select(AuditLog)
            .where(
                AuditLog.company_id == company_id,
                AuditLog.scope == AuditScope.COMPANY.value,
            )
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
        )
        return list(self._session.scalars(statement).all())
