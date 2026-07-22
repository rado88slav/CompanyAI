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
        "credential",
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
        actor_administrator_id: UUID,
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
        if resource_type != "company":
            raise ValueError("Company audit resource_type must be 'company'.")
        _validate_safe_details(details)
        return self._repository.create(
            scope=AuditScope.COMPANY.value,
            company_id=company_id,
            actor_type=AuditActorType.ADMINISTRATOR.value,
            actor_administrator_id=actor_administrator_id,
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


def get_audit_log_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> AuditLogService:
    """Create a request-scoped audit service."""

    return AuditLogService(AuditLogRepository(session))
