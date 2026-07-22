"""Application service for append-only audit events."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.audit_log import (
    AuditAction,
    AuditActorType,
    AuditLog,
    AuditScope,
)
from app.repositories.audit_log import AuditLogRepository

_FORBIDDEN_DETAIL_KEY_PARTS = frozenset(
    {
        "api_key",
        "authorization",
        "cookie",
        "encryption_key",
        "hash",
        "password",
        "secret",
        "signing_key",
        "token",
    }
)


def _validate_safe_details(value: Any, *, path: str = "details") -> None:
    """Reject non-JSON values and keys that may carry secrets."""

    if isinstance(value, dict):
        for key, nested_value in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} keys must be strings.")
            normalized_key = key.strip().lower().replace("-", "_")
            if any(part in normalized_key for part in _FORBIDDEN_DETAIL_KEY_PARTS):
                raise ValueError(f"Unsafe audit detail key: {path}.{key}")
            _validate_safe_details(nested_value, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, nested_value in enumerate(value):
            _validate_safe_details(nested_value, path=f"{path}[{index}]")
        return
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    raise ValueError(f"{path} contains a non-JSON value.")


class AuditLogService:
    """Append safe audit events and list isolated company activity."""

    def __init__(self, repository: AuditLogRepository) -> None:
        self._repository = repository

    def append_company_event(
        self,
        *,
        company_id: UUID,
        actor_administrator_id: UUID | None,
        action: str,
        resource_type: str,
        resource_id: UUID | None,
        details: dict[str, Any],
    ) -> AuditLog:
        """Append a normalized company event without committing."""

        if not isinstance(details, dict):
            raise ValueError("Audit details must be a JSON object.")
        try:
            normalized_action = AuditAction(action).value
        except ValueError as exc:
            raise ValueError("Unsupported company audit action.") from exc
        if resource_type not in {"company", "company_membership", "approval_request", "approval_decision", "authorization_policy", "authorization_usage", "agent", "agent_credential", "agent_permission"}:
            raise ValueError("Unsupported company audit resource_type.")
        _validate_safe_details(details)
        return self._repository.create(
            scope=AuditScope.COMPANY.value,
            company_id=company_id,
            actor_type=(AuditActorType.ADMINISTRATOR.value if actor_administrator_id is not None else AuditActorType.SYSTEM.value),
            actor_administrator_id=actor_administrator_id,
            actor_agent_id=None,
            action=normalized_action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )

    def list_company_activity(
        self,
        *,
        company_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[AuditLog], int]:
        """Return one isolated page of company activity."""

        events = self._repository.list_for_company(
            company_id=company_id,
            limit=limit,
            offset=offset,
        )
        total = self._repository.count_for_company(company_id=company_id)
        return events, total

    def append_platform_event(self, *, actor_administrator_id: UUID, action: str, resource_type: str, resource_id: UUID | None, details: dict[str, Any]) -> AuditLog:
        """Append a controlled platform event without committing."""
        if action not in {AuditAction.AUTHORIZATION_POLICY_CREATED.value, AuditAction.AUTHORIZATION_POLICY_REVOKED.value}:
            raise ValueError("Unsupported platform audit action.")
        if resource_type != "authorization_policy":
            raise ValueError("Unsupported platform audit resource_type.")
        _validate_safe_details(details)
        return self._repository.create(scope=AuditScope.PLATFORM.value, company_id=None, actor_type=AuditActorType.ADMINISTRATOR.value, actor_administrator_id=actor_administrator_id, action=action, resource_type=resource_type, resource_id=resource_id, details=details)

    def append_agent_event(self, *, company_id: UUID, actor_agent_id: UUID, action: str, resource_type: str, resource_id: UUID | None, details: dict[str, Any]) -> AuditLog:
        """Append a safe company event performed by an authenticated agent."""
        if action != AuditAction.AGENT_AUTHENTICATED.value or resource_type != "agent":
            raise ValueError("Unsupported agent audit event.")
        _validate_safe_details(details)
        return self._repository.create(scope=AuditScope.COMPANY.value, company_id=company_id, actor_type=AuditActorType.AGENT.value, actor_administrator_id=None, actor_agent_id=actor_agent_id, action=action, resource_type=resource_type, resource_id=resource_id, details=details)


def get_audit_log_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> AuditLogService:
    """Create a request-scoped audit service."""

    return AuditLogService(AuditLogRepository(session))
