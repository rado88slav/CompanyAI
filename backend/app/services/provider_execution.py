from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4
from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.provider_execution import DryRunProviderAdapter, ExecutionMode, UnsupportedProviderAdapter, provider_operation_registry
from app.db.session import get_db_session
from app.models.administrator import Administrator
from app.models.audit_log import AuditAction
from app.models.provider_execution import ProviderExecution, ProviderExecutionAttempt
from app.repositories.audit_log import AuditLogRepository
from app.repositories.provider_connection import ProviderConnectionRepository
from app.repositories.provider_execution import ProviderExecutionRepository
from app.services.audit_log import AuditLogService
from app.repositories.tool_registry import ToolRegistryRepository
from app.repositories.approval import ApprovalRepository, AuthorizationRepository
from app.schemas.approval import AuthorizationAction, ReservationCreate
from app.services.authorization_evaluator import AuthorizationDeniedError, AuthorizationEvaluatorService

class ExecutionNotFoundError(Exception): pass
class ExecutionConflictError(Exception): pass
class ExecutionDeniedError(Exception): pass
class ExecutionValidationError(Exception): pass

def _redact(value):
    if isinstance(value, dict): return {k: ("[REDACTED]" if any(part in k.casefold() for part in ("secret","token","password","api_key","credential","authorization","cookie","refresh")) else _redact(v)) for k,v in value.items()}
    if isinstance(value, list): return [_redact(v) for v in value]
    if isinstance(value, tuple): return tuple(_redact(v) for v in value)
    return value

class ProviderExecutionService:
    def __init__(self, session: Session):
        self.session=session; self.repo=ProviderExecutionRepository(session); self.connections=ProviderConnectionRepository(session); self.audit=AuditLogService(AuditLogRepository(session)); self.tools=ToolRegistryRepository(session); self.authorizer=AuthorizationEvaluatorService(ApprovalRepository(session), AuthorizationRepository(session), self.audit, session)
    def _append_event(self, *, item: ProviderExecution, administrator: Administrator | None, agent_id: UUID | None, action: str, details: dict) -> None:
        self.audit.append_company_event(
            company_id=item.company_id,
            actor_administrator_id=administrator.id if administrator else None,
            actor_agent_id=agent_id,
            action=action,
            resource_type="provider_execution",
            resource_id=item.id,
            details=details,
        )
    def create(self, *, company_id: UUID, data, administrator: Administrator | None=None, agent_id: UUID | None=None):
        if (administrator is None) == (agent_id is None): raise ExecutionValidationError
        descriptor=provider_operation_registry.require(data.provider_key, data.operation_key)
        if data.execution_mode == ExecutionMode.LIVE: raise ExecutionDeniedError("live_execution_not_implemented")
        connection=self.connections.connection(company_id=company_id, connection_id=data.provider_connection_id)
        if connection is None or connection.provider_key != descriptor.provider_key or connection.status != "active": raise ExecutionDeniedError("connection_not_effective")
        credential = self.connections.active_credential(company_id=company_id, connection_id=connection.id)
        if credential is None or (credential.expires_at is not None and credential.expires_at <= datetime.now(UTC)): raise ExecutionDeniedError("credential_not_effective")
        if agent_id is not None:
            allowed = any(tool.key == f"provider.{descriptor.provider_key}.{descriptor.operation_key}" for _grant, tool in self.tools.list_effective_grants(company_id=company_id, agent_id=agent_id))
            if not allowed: raise ExecutionDeniedError("tool_grant_required")
        existing=self.repo.by_key(company_id,data.idempotency_key)
        safe_payload = _redact(data.request_payload)
        if existing is not None:
            if (existing.provider_connection_id != data.provider_connection_id or existing.provider_key != data.provider_key or existing.operation_key != data.operation_key or existing.execution_mode != data.execution_mode.value or existing.request_payload != safe_payload): raise ExecutionConflictError("idempotency_key_conflict")
            return existing
        item=ProviderExecution(company_id=company_id, provider_connection_id=connection.id, provider_key=data.provider_key, operation_key=data.operation_key, execution_mode=data.execution_mode.value, status="authorized" if not descriptor.approval_required else "pending_authorization", requested_by_administrator_id=administrator.id if administrator else None, requested_by_agent_id=agent_id, idempotency_key=data.idempotency_key, request_payload=safe_payload, result_metadata={})
        try:
            self.repo.add(item); self._append_event(item=item, administrator=administrator, agent_id=agent_id, action=AuditAction.PROVIDER_EXECUTION_REQUESTED.value, details={"provider_key":item.provider_key,"operation_key":item.operation_key,"execution_mode":item.execution_mode}); self.session.commit(); return item
        except IntegrityError as exc: self.session.rollback(); raise ExecutionConflictError from exc
    def execute_dry_run(self, *, company_id: UUID, execution_id: UUID, administrator: Administrator | None=None, agent_id: UUID | None=None, authorization_policy_id: UUID | None=None):
        item=self.repo.get(company_id,execution_id,lock=True)
        if item is None: raise ExecutionNotFoundError
        if (administrator is None) == (agent_id is None): raise ExecutionValidationError
        if item.requested_by_administrator_id != (administrator.id if administrator else None) or item.requested_by_agent_id != agent_id: raise ExecutionDeniedError("requester_mismatch")
        descriptor=provider_operation_registry.require(item.provider_key,item.operation_key)
        usage = None
        if descriptor.approval_required and item.status == "pending_authorization":
            action=AuthorizationAction(company_id=company_id, actor_type="administrator" if administrator else "agent", actor_administrator_id=administrator.id if administrator else None, actor_agent_id=agent_id, action_type=f"provider.execute.{item.provider_key}.{item.operation_key}", tool_identifier=f"provider.{item.provider_key}.{item.operation_key}", risk_level=descriptor.risk_level.value, scope_type="company", scope_id=company_id, target_resource_type="provider_connection", target_resource_id=item.provider_connection_id, provider_connection_id=item.provider_connection_id)
            try:
                decision=self.authorizer.evaluate(action)
                if decision.status != "authorized" or decision.policy_id is None or (authorization_policy_id is not None and decision.policy_id != authorization_policy_id):
                    raise AuthorizationDeniedError(decision.reason_code)
                usage=self.authorizer.reserve(ReservationCreate(action=action, policy_id=decision.policy_id, reservation_key=item.id, execution_id=item.id, reservation_expires_at=datetime.now(UTC)+timedelta(minutes=5)), commit=False)
            except (AuthorizationDeniedError, IntegrityError) as exc:
                self.session.rollback()
                reason_code = exc.args[0] if exc.args else "authorization_required"
                self._append_event(item=item, administrator=administrator, agent_id=agent_id, action=AuditAction.PROVIDER_EXECUTION_DENIED.value, details={"reason_code": str(reason_code), "operation_key": item.operation_key})
                self.session.commit()
                raise ExecutionDeniedError("authorization_required") from exc
            item.authorization_reference=decision.policy_id; item.status="authorized"
            self._append_event(item=item, administrator=administrator, agent_id=agent_id, action=AuditAction.PROVIDER_EXECUTION_AUTHORIZED.value, details={"policy_id":str(decision.policy_id),"usage_id":str(usage.id),"operation_key":item.operation_key})
        if item.status not in {"authorized"}: raise ExecutionConflictError
        now=datetime.now(UTC); item.status="running"; item.started_at=now; attempt=ProviderExecutionAttempt(company_id=company_id,provider_execution_id=item.id,attempt_number=1,status="running",adapter_name="dry-run",request_metadata={},response_metadata={},error_metadata={},started_at=now); self.repo.add_attempt(attempt)
        self._append_event(item=item, administrator=administrator, agent_id=agent_id, action=AuditAction.PROVIDER_EXECUTION_STARTED.value, details={"operation_key":item.operation_key,"attempt_number":1})
        try:
            result=DryRunProviderAdapter().execute(provider_operation_registry.require(item.provider_key,item.operation_key), item.request_payload, idempotency_key=item.idempotency_key)
            item.result_metadata=result; item.status="succeeded"; item.completed_at=datetime.now(UTC); attempt.status="succeeded"; attempt.completed_at=item.completed_at
            if usage is not None: self.authorizer.transition(company_id=company_id,usage_id=usage.id,status="succeeded",actor_administrator_id=administrator.id if administrator else None,actor_agent_id=agent_id,commit=False)
            self._append_event(item=item, administrator=administrator, agent_id=agent_id, action=AuditAction.PROVIDER_EXECUTION_SUCCEEDED.value, details={"operation_key":item.operation_key}); self.session.commit(); return item
        except Exception as exc:
            now = datetime.now(UTC)
            item.status = "failed"; item.completed_at = now; item.error_category = "provider_error"; item.error_message = "Provider execution failed."
            attempt.status = "failed"; attempt.completed_at = now; attempt.error_metadata = {"category": "provider_error"}
            if usage is not None:
                self.authorizer.transition(company_id=company_id, usage_id=usage.id, status="failed", actor_administrator_id=administrator.id if administrator else None, actor_agent_id=agent_id, failure_code="provider_error", commit=False)
            self._append_event(item=item, administrator=administrator, agent_id=agent_id, action=AuditAction.PROVIDER_EXECUTION_FAILED.value, details={"operation_key": item.operation_key, "category": "provider_error"})
            self.session.commit()
            raise ExecutionConflictError("provider_execution_failed") from exc
    def list(self, company_id, limit, offset): return self.repo.list(company_id,limit,offset), self.repo.count(company_id)
    def available_operations(self, *, company_id: UUID, agent_id: UUID):
        keys={tool.key for _grant, tool in self.tools.list_effective_grants(company_id=company_id, agent_id=agent_id)}
        return [item for item in provider_operation_registry.all() if f"provider.{item.provider_key}.{item.operation_key}" in keys]
    def get(self, company_id, execution_id):
        item=self.repo.get(company_id,execution_id)
        if item is None: raise ExecutionNotFoundError
        return item
    def cancel(self, *, company_id: UUID, execution_id: UUID, administrator: Administrator) -> ProviderExecution:
        item=self.repo.get(company_id, execution_id, lock=True)
        if item is None: raise ExecutionNotFoundError
        if item.status not in {"pending_authorization", "authorized", "running"}: raise ExecutionConflictError("terminal_state")
        item.status="cancelled"; item.cancelled_at=datetime.now(UTC)
        self.audit.append_company_event(company_id=company_id, actor_administrator_id=administrator.id, action=AuditAction.PROVIDER_EXECUTION_CANCELLED.value, resource_type="provider_execution", resource_id=item.id, details={"operation_key": item.operation_key})
        self.session.commit(); return item

def get_provider_execution_service(session: Annotated[Session, Depends(get_db_session)]): return ProviderExecutionService(session)
