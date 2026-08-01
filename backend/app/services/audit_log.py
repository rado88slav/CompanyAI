"""Application service for append-only audit events."""

from datetime import datetime
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
from app.schemas.activity import ActivityEventResponse

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

_SAFE_DETAIL_KEYS = frozenset(
    {
        "connection_id",
        "provider_key",
        "status",
        "development_only",
        "live_delivery",
        "tool_key",
        "category",
        "risk_level",
        "requires_approval",
        "inbound_email_id",
        "reply_proposal_id",
        "approval_request_id",
        "outbound_email_id",
        "recipient_domain",
        "subject_present",
        "changed",
        "role",
        "is_active",
        "operation",
        "operation_key",
        "execution_mode",
        "reason_code",
        "protocol",
        "sandbox",
        "dry_run",
        "provider_message_id",
        "seed_key",
        "task_key",
        "proposal_type",
        "authorization_status",
        "runtime_type",
        "denied_reason",
        "message_digest",
        "provider_execution_id",
        "simulation_only",
        "live_send_available",
        "attempt_number",
        "usage_id",
        "policy_id",
        "selected_by",
        "target_active",
        "target_superuser",
        "session_revocation_supported",
        "recipient_count",
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


def _category(resource_type: str, action: str) -> str:
    if resource_type.startswith("approval") or resource_type.startswith("authorization"):
        return "approval"
    if resource_type.startswith("provider"):
        return "provider"
    if resource_type.startswith("email") or resource_type in {"inbound_email", "outbound_email"}:
        return "email"
    if resource_type.startswith("agent") or action.startswith("agent"):
        return "agent"
    if resource_type == "company":
        return "system"
    return "system"


def _status(action: str) -> str:
    suffix = action.rsplit(".", maxsplit=1)[-1]
    if suffix in {"failed", "denied", "cancelled", "revoked"}:
        return suffix
    if suffix in {"succeeded", "sent", "approved", "activated", "authenticated"}:
        return "succeeded"
    if suffix in {"created", "updated", "submitted", "drafted", "requested", "reserved", "started"}:
        return "recorded"
    return "recorded"


def _severity(action: str) -> str:
    suffix = action.rsplit(".", maxsplit=1)[-1]
    if suffix == "failed":
        return "error"
    if suffix in {"denied", "cancelled", "revoked"}:
        return "warning"
    return "info"


def _humanize(value: str) -> str:
    return value.replace("_", " ").replace(".", " ").title()


def _summary(event: AuditLog, category: str) -> str:
    resource = _humanize(event.resource_type)
    action = event.action.rsplit(".", maxsplit=1)[-1].replace("_", " ")
    if category == "agent":
        return f"Agent activity was {action} for this company."
    if category == "approval":
        return f"Approval workflow {action} on {resource.lower()}."
    if category == "provider":
        return f"Provider operation {action} on {resource.lower()}."
    if category == "email":
        return f"Email workflow {action} on {resource.lower()}."
    return f"{resource} activity was {action}."


def _safe_details(details: dict[str, Any]) -> dict[str, str | int | float | bool | None]:
    safe: dict[str, str | int | float | bool | None] = {}
    for key, value in details.items():
        if key not in _SAFE_DETAIL_KEYS:
            continue
        if value is None or isinstance(value, (str, int, float, bool)):
            safe[key] = value
    return safe


def _map_activity_event(event: AuditLog) -> ActivityEventResponse:
    category = _category(event.resource_type, event.action)
    return ActivityEventResponse(
        id=event.id,
        company_id=event.company_id,
        occurred_at=event.created_at,
        category=category,
        source=event.action.split(".", maxsplit=1)[0],
        action=event.action,
        title=f"{_humanize(event.action)}",
        summary=_summary(event, category),
        status=_status(event.action),
        severity=_severity(event.action),
        actor_display=_humanize(event.actor_type),
        entity_type=event.resource_type,
        entity_id=event.resource_id,
        safe_details=_safe_details(event.details),
        correlation_id=str(event.resource_id) if event.resource_id else None,
    )


class AuditLogService:
    """Append safe audit events and list isolated company activity."""

    def __init__(self, repository: AuditLogRepository) -> None:
        self._repository = repository

    def append_company_event(
        self,
        *,
        company_id: UUID,
        actor_administrator_id: UUID | None,
        actor_agent_id: UUID | None = None,
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
        if resource_type not in {"company", "company_membership", "approval_request", "approval_decision", "authorization_policy", "authorization_usage", "agent", "agent_manager", "agent_credential", "agent_permission", "tool_definition", "company_tool", "agent_tool_grant", "provider_connection", "provider_credential", "provider_execution", "inbound_email", "email_reply_proposal", "outbound_email", "email_automation", "email_single_message_test"}:
            raise ValueError("Unsupported company audit resource_type.")
        _validate_safe_details(details)
        if actor_administrator_id is not None and actor_agent_id is not None:
            raise ValueError("A company audit event must have at most one actor.")
        actor_type = AuditActorType.SYSTEM.value
        if actor_administrator_id is not None:
            actor_type = AuditActorType.ADMINISTRATOR.value
        elif actor_agent_id is not None:
            actor_type = AuditActorType.AGENT.value
        return self._repository.create(
            scope=AuditScope.COMPANY.value,
            company_id=company_id,
            actor_type=actor_type,
            actor_administrator_id=actor_administrator_id,
            actor_agent_id=actor_agent_id,
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
        event_type: str | None = None,
        source: str | None = None,
        severity: str | None = None,
        actor: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[ActivityEventResponse], int]:
        """Return one isolated page of company activity."""

        events = self._repository.list_for_company(
            company_id=company_id,
            limit=limit,
            offset=offset,
            event_type=event_type,
            source=source,
            severity=severity,
            actor=actor,
            date_from=date_from,
            date_to=date_to,
        )
        total = self._repository.count_for_company(
            company_id=company_id,
            event_type=event_type,
            source=source,
            severity=severity,
            actor=actor,
            date_from=date_from,
            date_to=date_to,
        )
        return [_map_activity_event(event) for event in events], total

    def append_platform_event(self, *, actor_administrator_id: UUID, action: str, resource_type: str, resource_id: UUID | None, details: dict[str, Any]) -> AuditLog:
        """Append a controlled platform event without committing."""
        if action not in {AuditAction.AUTHORIZATION_POLICY_CREATED.value, AuditAction.AUTHORIZATION_POLICY_REVOKED.value, AuditAction.TOOL_DEFINITION_CREATED.value, AuditAction.TOOL_DEFINITION_UPDATED.value, AuditAction.TOOL_DEFINITION_ACTIVATED.value, AuditAction.TOOL_DEFINITION_DEACTIVATED.value, AuditAction.TOOL_DEFINITION_DEPRECATED.value}:
            raise ValueError("Unsupported platform audit action.")
        if resource_type not in {"authorization_policy", "tool_definition"}:
            raise ValueError("Unsupported platform audit resource_type.")
        _validate_safe_details(details)
        return self._repository.create(scope=AuditScope.PLATFORM.value, company_id=None, actor_type=AuditActorType.ADMINISTRATOR.value, actor_administrator_id=actor_administrator_id, action=action, resource_type=resource_type, resource_id=resource_id, details=details)

    def append_platform_system_event(self, *, action: str, resource_type: str, resource_id: UUID | None, details: dict[str, Any]) -> AuditLog:
        """Append a controlled unauthenticated local-system recovery event."""
        if action != AuditAction.ADMINISTRATOR_PASSWORD_RESET.value:
            raise ValueError("Unsupported platform system audit action.")
        if resource_type != "administrator":
            raise ValueError("Unsupported platform system audit resource_type.")
        _validate_safe_details(details)
        return self._repository.create(scope=AuditScope.PLATFORM.value, company_id=None, actor_type=AuditActorType.SYSTEM.value, actor_administrator_id=None, action=action, resource_type=resource_type, resource_id=resource_id, details=details)

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
