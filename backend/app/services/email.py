"""Transactional service for the thin local-test email workflow."""

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.authorization import AuthorizationMode, RiskLevel
from app.core.credential_encryption import CredentialEncryptionService
from app.core.provider_execution import DryRunProviderAdapter, ExecutionMode, LocalTestEmailAdapter, provider_operation_registry
from app.db.session import get_db_session
from app.models.administrator import Administrator
from app.models.approval import ApprovalRequest
from app.models.audit_log import AuditAction
from app.models.company_setting import CompanySetting
from app.models.email import EmailReplyProposal, InboundEmail, OutboundEmail
from app.models.provider_execution import ProviderExecution, ProviderExecutionAttempt
from app.repositories.approval import ApprovalRepository, AuthorizationRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.email import EmailRepository
from app.repositories.provider_connection import ProviderConnectionRepository
from app.repositories.provider_execution import ProviderExecutionRepository
from app.repositories.agent import AgentRepository
from app.schemas.approval import ApprovalDecisionCreate, ApprovalRequestCreate, AuthorizationAction, AuthorizationConditionsV1, ReservationCreate
from app.schemas.email import EmailSandboxEmergencyStopUpdate, EmailSandboxStatusResponse, ReplyProposalWrite, SendReplyRequest, SingleMessageApprovalRequest, SingleMessageApprovalResponse, SingleMessageApprovalReview, SingleMessageApprovalReviewList, SingleMessageLiveExecutionRequest, SingleMessageLiveExecutionResponse, SingleMessageMode, SingleMessagePreviewRequest, SingleMessagePreviewResponse, SingleMessageRecipientAllowlistUpdate, SingleMessageRecipientAllowlistResponse, SingleMessageSenderAllowlistUpdate, SingleMessageSimulationRequest, SingleMessageSimulationResponse, TestInboundEmailImport, normalize_email
from app.services.authorization_evaluator import AuthorizationDeniedError, AuthorizationEvaluatorService
from app.services.generic_smtp_imap import GENERIC_MAILBOX_HEALTH_KEY, GenericSmtpLiveTransport, MailboxSendAuthenticationError, MailboxSendError, MailboxSendOutcomeUncertainError, MailboxSendResult
from app.services.approval_manager import ApprovalManagerService
from app.services.audit_log import AuditLogService


class EmailNotFoundError(Exception): pass
class EmailConflictError(Exception): pass
class EmailForbiddenError(Exception): pass
class EmailSandboxRejectedError(EmailForbiddenError):
    def __init__(self, reason_code: str, policy_checks: dict[str, bool] | None = None) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.policy_checks = policy_checks or {}


SINGLE_MESSAGE_SCHEMA = "email_single_message_test.v1"
SINGLE_MESSAGE_PREFIX = "[COMPANYAI TEST]"
DISABLED_SINGLE_MESSAGE_FEATURES = ["cc", "bcc", "attachments", "tracking", "follow_ups", "recipient_lists", "automatic_retry"]
LIVE_CONFIRMATION_TEXT = "SEND ONE TEST EMAIL"


def content_digest(recipient: str, subject: str, body: str) -> str:
    canonical = json.dumps(
        {"body": body, "recipient_email": recipient.casefold(), "subject": subject},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def single_message_digest(*, provider_connection_id: UUID, sender_email: str, recipient_email: str, subject: str, body: str) -> str:
    canonical = json.dumps(
        {
            "body": body,
            "provider_connection_id": str(provider_connection_id),
            "recipient_email": recipient_email.casefold(),
            "sender_email": sender_email.casefold(),
            "subject": subject,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def reply_subject(subject: str) -> str:
    normalized = re.sub(r"^(?:\s*re\s*:\s*)+", "", subject, flags=re.IGNORECASE).strip()
    return f"Re: {normalized}" if normalized else "Re:"


class EmailWorkflowService:
    def __init__(self, session: Session, encryption: CredentialEncryptionService | None = None, smtp_live_transport: GenericSmtpLiveTransport | None = None) -> None:
        self.session = session
        self.repo = EmailRepository(session)
        self.approvals = ApprovalRepository(session)
        self.authorizations = AuthorizationRepository(session)
        self.connections = ProviderConnectionRepository(session)
        self.executions = ProviderExecutionRepository(session)
        self.audit = AuditLogService(AuditLogRepository(session))
        self.approval_service = ApprovalManagerService(self.approvals, self.authorizations, self.audit, session, AgentRepository(session))
        self.encryption = encryption
        self.smtp_live_transport = smtp_live_transport or GenericSmtpLiveTransport()

    def _event(self, company_id: UUID, actor: Administrator, action: AuditAction, resource_type: str, resource_id: UUID, details: dict) -> None:
        self.audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=action.value, resource_type=resource_type, resource_id=resource_id, details=details)

    def _sandbox_policy(self, company_id: UUID) -> dict:
        setting = self.session.scalar(
            select(CompanySetting).where(
                CompanySetting.company_id == company_id,
                CompanySetting.category == "email_sandbox",
                CompanySetting.key == "policy",
            )
        )
        if setting is not None and isinstance(setting.value, dict):
            return setting.value
        return {
            "enabled": True,
            "recipient_allowlist": [],
            "sender_allowlist": [],
            "max_recipients_per_message": 1,
            "max_messages_per_hour": 5,
            "max_messages_per_day": 10,
            "required_subject_prefix": "[COMPANYAI TEST]",
            "approval_required": True,
            "emergency_stop": False,
            "followups_enabled": False,
            "bulk_sending_enabled": False,
            "attachments_enabled": False,
        }

    def _sent_count_since(self, company_id: UUID, since: datetime) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(OutboundEmail)
                .where(
                    OutboundEmail.company_id == company_id,
                    OutboundEmail.status == "sent",
                    OutboundEmail.sent_at >= since,
                )
            )
            or 0
        )

    def _single_message_policy(self, company_id: UUID) -> dict:
        policy = self._sandbox_policy(company_id)
        return {
            **policy,
            "enabled": bool(policy.get("enabled", True)),
            "required_subject_prefix": str(policy.get("required_subject_prefix") or SINGLE_MESSAGE_PREFIX),
            "recipient_allowlist": policy.get("recipient_allowlist", []),
            "sender_allowlist": policy.get("sender_allowlist", []),
            "max_recipients_per_message": int(policy.get("max_recipients_per_message", 1)),
            "max_messages_per_hour": int(policy.get("max_messages_per_hour", 5)),
            "max_messages_per_day": int(policy.get("max_messages_per_day", 10)),
            "working_hours": policy.get("working_hours"),
            "approval_required": bool(policy.get("approval_required", True)),
            "emergency_stop": bool(policy.get("emergency_stop", False)),
            "followups_enabled": bool(policy.get("followups_enabled", False)),
            "bulk_sending_enabled": bool(policy.get("bulk_sending_enabled", False)),
            "attachments_enabled": bool(policy.get("attachments_enabled", False)),
        }

    def email_sandbox_status(self, *, company_id: UUID) -> EmailSandboxStatusResponse:
        policy = self._single_message_policy(company_id)
        return self._sandbox_status_from_policy(policy)

    def _sandbox_status_from_policy(self, policy: dict) -> EmailSandboxStatusResponse:
        recipients = sorted(self._exact_allowlist(policy.get("recipient_allowlist", [])))
        senders = sorted(self._exact_allowlist(policy.get("sender_allowlist", [])))
        emergency_stop = bool(policy.get("emergency_stop", False))
        return EmailSandboxStatusResponse(
            recipient_allowlist=recipients,
            sender_allowlist=senders,
            enabled=bool(policy.get("enabled", True)),
            emergency_stop=emergency_stop,
            emergency_stop_status="active" if emergency_stop else "inactive",
            max_recipients_per_message=int(policy.get("max_recipients_per_message", 1)),
            max_messages_per_hour=int(policy.get("max_messages_per_hour", 5)),
            max_messages_per_day=int(policy.get("max_messages_per_day", 10)),
            required_subject_prefix=str(policy.get("required_subject_prefix") or SINGLE_MESSAGE_PREFIX),
            approval_required=bool(policy.get("approval_required", True)),
            followups_enabled=bool(policy.get("followups_enabled", False)),
            bulk_sending_enabled=bool(policy.get("bulk_sending_enabled", False)),
            attachments_enabled=bool(policy.get("attachments_enabled", False)),
            disabled_features=DISABLED_SINGLE_MESSAGE_FEATURES,
        )

    def single_message_recipient_allowlist(self, *, company_id: UUID) -> SingleMessageRecipientAllowlistResponse:
        recipients = sorted(self._exact_allowlist(self._single_message_policy(company_id).get("recipient_allowlist", [])))
        return SingleMessageRecipientAllowlistResponse(recipient_allowlist=recipients)

    def add_single_message_recipient_allowlist(self, *, company_id: UUID, data: SingleMessageRecipientAllowlistUpdate, actor: Administrator) -> SingleMessageRecipientAllowlistResponse:
        return self._update_single_message_recipient_allowlist(
            company_id=company_id,
            recipient_email=data.recipient_email,
            actor=actor,
            remove=False,
        )

    def remove_single_message_recipient_allowlist(self, *, company_id: UUID, data: SingleMessageRecipientAllowlistUpdate, actor: Administrator) -> SingleMessageRecipientAllowlistResponse:
        return self._update_single_message_recipient_allowlist(
            company_id=company_id,
            recipient_email=data.recipient_email,
            actor=actor,
            remove=True,
        )

    def add_single_message_sender_allowlist(self, *, company_id: UUID, data: SingleMessageSenderAllowlistUpdate, actor: Administrator) -> EmailSandboxStatusResponse:
        sender_email = self._sender_from_allowlist_update(company_id=company_id, data=data, actor=actor)
        return self._update_single_message_sender_allowlist(company_id=company_id, sender_email=sender_email, actor=actor, remove=False)

    def remove_single_message_sender_allowlist(self, *, company_id: UUID, data: SingleMessageSenderAllowlistUpdate, actor: Administrator) -> EmailSandboxStatusResponse:
        sender_email = self._sender_from_allowlist_update(company_id=company_id, data=data, actor=actor)
        return self._update_single_message_sender_allowlist(company_id=company_id, sender_email=sender_email, actor=actor, remove=True)

    def update_email_sandbox_emergency_stop(self, *, company_id: UUID, data: EmailSandboxEmergencyStopUpdate, actor: Administrator) -> EmailSandboxStatusResponse:
        try:
            setting, policy = self._locked_sandbox_policy(company_id)
            previous = bool(policy.get("emergency_stop", False))
            policy["emergency_stop"] = data.emergency_stop
            self._save_sandbox_policy_setting(company_id=company_id, setting=setting, policy=policy)
            self.audit.append_company_event(
                company_id=company_id,
                actor_administrator_id=actor.id,
                action=AuditAction.EMAIL_AUTOMATION_SETTINGS_UPDATED.value,
                resource_type="email_automation",
                resource_id=None,
                details={
                    "operation": "email_sandbox_emergency_stop_updated",
                    "changed": previous != data.emergency_stop,
                    "status": "active" if data.emergency_stop else "inactive",
                },
            )
            self.session.commit()
            return self._sandbox_status_from_policy(policy)
        except Exception:
            self.session.rollback()
            raise

    def _locked_sandbox_policy(self, company_id: UUID) -> tuple[CompanySetting | None, dict]:
        setting = self.session.scalar(
            select(CompanySetting).where(
                CompanySetting.company_id == company_id,
                CompanySetting.category == "email_sandbox",
                CompanySetting.key == "policy",
            ).with_for_update()
        )
        policy = dict(setting.value) if setting is not None and isinstance(setting.value, dict) else self._sandbox_policy(company_id)
        return setting, policy

    def _save_sandbox_policy_setting(self, *, company_id: UUID, setting: CompanySetting | None, policy: dict) -> None:
        if setting is None:
            setting = CompanySetting(company_id=company_id, category="email_sandbox", key="policy", value=policy)
            self.session.add(setting)
        else:
            setting.value = policy

    def _update_single_message_recipient_allowlist(self, *, company_id: UUID, recipient_email: str, actor: Administrator, remove: bool) -> SingleMessageRecipientAllowlistResponse:
        try:
            setting, policy = self._locked_sandbox_policy(company_id)
            recipients = self._exact_allowlist(policy.get("recipient_allowlist", []))
            previous = set(recipients)
            if remove:
                recipients.discard(recipient_email)
            else:
                recipients.add(recipient_email)
            policy["recipient_allowlist"] = sorted(recipients)
            self._save_sandbox_policy_setting(company_id=company_id, setting=setting, policy=policy)
            operation = "single_message_recipient_allowlist_removed" if remove else "single_message_recipient_allowlist_updated"
            self.audit.append_company_event(
                company_id=company_id,
                actor_administrator_id=actor.id,
                action=AuditAction.EMAIL_AUTOMATION_SETTINGS_UPDATED.value,
                resource_type="email_automation",
                resource_id=None,
                details={
                    "operation": operation,
                    "changed": previous != recipients,
                    "recipient_count": len(recipients),
                },
            )
            self.session.commit()
            return SingleMessageRecipientAllowlistResponse(recipient_allowlist=policy["recipient_allowlist"])
        except Exception:
            self.session.rollback()
            raise

    def _update_single_message_sender_allowlist(self, *, company_id: UUID, sender_email: str, actor: Administrator, remove: bool) -> EmailSandboxStatusResponse:
        try:
            setting, policy = self._locked_sandbox_policy(company_id)
            senders = self._exact_allowlist(policy.get("sender_allowlist", []))
            previous = set(senders)
            if remove:
                senders.discard(sender_email)
            else:
                senders.add(sender_email)
            policy["sender_allowlist"] = sorted(senders)
            self._save_sandbox_policy_setting(company_id=company_id, setting=setting, policy=policy)
            operation = "single_message_sender_allowlist_removed" if remove else "single_message_sender_allowlist_updated"
            self.audit.append_company_event(
                company_id=company_id,
                actor_administrator_id=actor.id,
                action=AuditAction.EMAIL_AUTOMATION_SETTINGS_UPDATED.value,
                resource_type="email_automation",
                resource_id=None,
                details={
                    "operation": operation,
                    "changed": previous != senders,
                    "sender_count": len(senders),
                },
            )
            self.session.commit()
            return self._sandbox_status_from_policy(policy)
        except Exception:
            self.session.rollback()
            raise

    def _sender_from_allowlist_update(self, *, company_id: UUID, data: SingleMessageSenderAllowlistUpdate, actor: Administrator) -> str:
        if data.sender_email is not None:
            return data.sender_email
        if data.provider_connection_id is None:
            raise EmailConflictError
        _connection, sender_email = self._mailbox_sender(company_id=company_id, provider_connection_id=data.provider_connection_id, actor=actor)
        return sender_email

    def _exact_allowlist(self, values: object) -> set[str]:
        if not isinstance(values, list):
            return set()
        normalized: set[str] = set()
        for value in values:
            if not isinstance(value, str):
                continue
            candidate = value.strip().casefold()
            if "*" in candidate or candidate.startswith("@") or "," in candidate or ";" in candidate:
                continue
            try:
                normalized.add(normalize_email(candidate))
            except ValueError:
                continue
        return normalized

    def _reject_single_message(self, company_id: UUID, actor: Administrator, reason_code: str, resource_id: UUID | None = None, policy_checks: dict[str, bool] | None = None) -> None:
        self.audit.append_company_event(
            company_id=company_id,
            actor_administrator_id=actor.id,
            action=AuditAction.PROVIDER_EXECUTION_DENIED.value,
            resource_type="email_single_message_test",
            resource_id=resource_id,
            details={"operation_key": "send_email", "reason_code": reason_code, "sandbox": True, "simulation_only": True},
        )
        self.session.commit()
        raise EmailSandboxRejectedError(reason_code, policy_checks=policy_checks)

    def _mailbox_sender(self, *, company_id: UUID, provider_connection_id: UUID, actor: Administrator) -> tuple[object, str]:
        connection = self.connections.connection(company_id=company_id, connection_id=provider_connection_id, for_update=True)
        if connection is None or connection.provider_key != "generic_smtp_imap" or connection.status != "active":
            self._reject_single_message(company_id, actor, "mailbox_not_active")
        credential = self.connections.active_credential(company_id=company_id, connection_id=connection.id, for_update=True)
        if credential is None or (credential.expires_at is not None and credential.expires_at <= datetime.now(UTC)):
            self._reject_single_message(company_id, actor, "credential_not_active")
        health = connection.metadata_.get(GENERIC_MAILBOX_HEALTH_KEY)
        smtp = health.get("smtp") if isinstance(health, dict) else None
        imap = health.get("imap") if isinstance(health, dict) else None
        if not isinstance(smtp, dict) or smtp.get("status") != "succeeded":
            self._reject_single_message(company_id, actor, "smtp_not_tested")
        if not isinstance(imap, dict) or imap.get("status") != "succeeded":
            self._reject_single_message(company_id, actor, "imap_not_tested")
        sender_email = str(connection.configuration.get("email_address") or "").strip().casefold()
        if not sender_email:
            self._reject_single_message(company_id, actor, "sender_missing")
        return connection, sender_email

    def _single_message_policy_checks(self, *, company_id: UUID, sender_email: str, data: SingleMessagePreviewRequest | SingleMessageApprovalRequest, policy: dict) -> dict[str, bool]:
        allowed_recipients = self._exact_allowlist(policy.get("recipient_allowlist", []))
        allowed_senders = self._exact_allowlist(policy.get("sender_allowlist", []))
        prefix = str(policy.get("required_subject_prefix") or SINGLE_MESSAGE_PREFIX).strip()
        return {
            "sandbox_enabled": bool(policy.get("enabled", True)),
            "mailbox_active": True,
            "mailbox_tested": True,
            "credential_active": True,
            "one_recipient_required": int(policy.get("max_recipients_per_message", 1)) == 1,
            "recipient_allowlisted": bool(allowed_recipients) and data.recipient_email.casefold() in allowed_recipients,
            "sender_allowlisted": bool(allowed_senders) and sender_email.casefold() in allowed_senders,
            "subject_prefix": not prefix or data.subject.startswith(prefix),
            "hourly_quota_available": self._sent_count_since(company_id, datetime.now(UTC) - timedelta(hours=1)) < int(policy.get("max_messages_per_hour", 5)),
            "daily_quota_available": self._sent_count_since(company_id, datetime.now(UTC) - timedelta(days=1)) < int(policy.get("max_messages_per_day", 10)),
            "working_hours": self._inside_working_hours(policy),
            "emergency_stop_disabled": not bool(policy.get("emergency_stop", False)),
            "approval_required": bool(policy.get("approval_required", True)),
        }

    def _enforce_single_message_policy(self, *, company_id: UUID, actor: Administrator, sender_email: str, data: SingleMessagePreviewRequest | SingleMessageApprovalRequest) -> tuple[dict, dict[str, bool]]:
        policy = self._single_message_policy(company_id)
        checks = self._single_message_policy_checks(company_id=company_id, sender_email=sender_email, data=data, policy=policy)
        failure_order = [
            ("sandbox_enabled", "sandbox_disabled"),
            ("one_recipient_required", "one_recipient_required"),
            ("recipient_allowlisted", "recipient_not_allowlisted"),
            ("sender_allowlisted", "sender_not_allowlisted"),
            ("subject_prefix", "subject_prefix_required"),
            ("hourly_quota_available", "hourly_quota_exceeded"),
            ("daily_quota_available", "daily_quota_exceeded"),
            ("working_hours", "outside_working_hours"),
        ]
        if data.mode is SingleMessageMode.LIVE_TEST:
            failure_order.insert(1, ("emergency_stop_disabled", "emergency_stop_enabled"))
        for key, reason_code in failure_order:
            if not checks[key]:
                self._reject_single_message(company_id, actor, reason_code, policy_checks=checks)
        return policy, checks

    def _inside_working_hours(self, policy: dict) -> bool:
        working = policy.get("working_hours")
        if working is None:
            return True
        if not isinstance(working, dict):
            return False
        try:
            zone = ZoneInfo(str(working.get("timezone") or "Europe/Sofia"))
        except ZoneInfoNotFoundError:
            return False
        now = datetime.now(UTC).astimezone(zone)
        weekdays = working.get("weekdays", [0, 1, 2, 3, 4])
        if now.weekday() not in {int(day) for day in weekdays}:
            return False
        start = str(working.get("start") or "09:00")
        end = str(working.get("end") or "17:00")
        current = now.time().isoformat(timespec="minutes")
        return start <= current < end

    def _single_message_preview(self, *, connection_id: UUID, sender_email: str, recipient_email: str, subject: str, body: str, idempotency_key: str, mode: SingleMessageMode, policy_checks: dict[str, bool]) -> SingleMessagePreviewResponse:
        digest = single_message_digest(provider_connection_id=connection_id, sender_email=sender_email, recipient_email=recipient_email, subject=subject, body=body)
        return SingleMessagePreviewResponse(
            provider_connection_id=connection_id,
            sender_email=sender_email,
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            payload_digest=digest,
            idempotency_key=idempotency_key,
            approval_required=True,
            simulation_only=mode is SingleMessageMode.SIMULATION,
            live_send_available=mode is SingleMessageMode.LIVE_TEST and policy_checks.get("emergency_stop_disabled", False),
            disabled_features=DISABLED_SINGLE_MESSAGE_FEATURES,
            mode=mode,
            policy_checks=policy_checks,
        )

    def preview_single_message(self, *, company_id: UUID, data: SingleMessagePreviewRequest, actor: Administrator) -> SingleMessagePreviewResponse:
        connection, sender_email = self._mailbox_sender(company_id=company_id, provider_connection_id=data.provider_connection_id, actor=actor)
        _policy, checks = self._enforce_single_message_policy(company_id=company_id, actor=actor, sender_email=sender_email, data=data)
        if self.executions.by_key(company_id, data.idempotency_key) is not None:
            self._reject_single_message(company_id, actor, "duplicate_idempotency_key")
        preview = self._single_message_preview(connection_id=connection.id, sender_email=sender_email, recipient_email=data.recipient_email, subject=data.subject, body=data.body, idempotency_key=data.idempotency_key, mode=data.mode, policy_checks=checks)
        self.audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.EMAIL_SINGLE_MESSAGE_SIMULATED.value, resource_type="email_single_message_test", resource_id=None, details={"message_digest": preview.payload_digest, "simulation_only": preview.simulation_only, "live_send_available": preview.live_send_available})
        self.session.commit()
        return preview

    def request_single_message_approval(self, *, company_id: UUID, data: SingleMessageApprovalRequest, actor: Administrator) -> SingleMessageApprovalResponse:
        connection, sender_email = self._mailbox_sender(company_id=company_id, provider_connection_id=data.provider_connection_id, actor=actor)
        _policy, checks = self._enforce_single_message_policy(company_id=company_id, actor=actor, sender_email=sender_email, data=data)
        if self.executions.by_key(company_id, data.idempotency_key) is not None:
            self._reject_single_message(company_id, actor, "duplicate_idempotency_key")
        preview = self._single_message_preview(connection_id=connection.id, sender_email=sender_email, recipient_email=data.recipient_email, subject=data.subject, body=data.body, idempotency_key=data.idempotency_key, mode=data.mode, policy_checks=checks)
        if preview.payload_digest != data.preview_payload_digest:
            raise EmailConflictError
        execution_mode = ExecutionMode.LIVE.value if data.mode is SingleMessageMode.LIVE_TEST else ExecutionMode.DRY_RUN.value
        execution = ProviderExecution(
            company_id=company_id,
            provider_connection_id=connection.id,
            provider_key="generic_smtp_imap",
            operation_key="send_email",
            execution_mode=execution_mode,
            status="pending_authorization",
            requested_by_administrator_id=actor.id,
            idempotency_key=data.idempotency_key,
            request_payload={
                "payload_schema": SINGLE_MESSAGE_SCHEMA,
                "mode": data.mode.value,
                "sender_email": sender_email,
                "recipient_email": data.recipient_email,
                "subject": data.subject,
                "body": data.body,
                "payload_digest": preview.payload_digest,
                "confirmation_text": data.confirmation_text,
            },
            result_metadata={"simulation_only": preview.simulation_only, "live_send_available": preview.live_send_available},
        )
        try:
            self.executions.add(execution)
            approval = self.approval_service.create_request(company_id=company_id, actor=actor, commit=False, payload=ApprovalRequestCreate(
                authorization_mode=AuthorizationMode.APPROVE_SINGLE_ACTION,
                action_type="provider.execute.generic_smtp_imap.send_email",
                tool_identifier="provider.generic_smtp_imap.send_email",
                risk_level=RiskLevel.HIGH,
                scope_type="company",
                scope_id=company_id,
                target_resource_type="provider_execution",
                target_resource_id=execution.id,
                provider_connection_id=connection.id,
                requested_conditions=AuthorizationConditionsV1(payload_schema=SINGLE_MESSAGE_SCHEMA, payload_digest=preview.payload_digest),
                reason="Approve exactly one controlled CompanyAI test email simulation." if preview.simulation_only else "Approve exactly one controlled CompanyAI LIVE TEST email.",
            ))
            self.audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.PROVIDER_EXECUTION_REQUESTED.value, resource_type="provider_execution", resource_id=execution.id, details={"provider_key": "generic_smtp_imap", "operation_key": "send_email", "execution_mode": execution_mode, "simulation_only": preview.simulation_only, "live_send_available": preview.live_send_available})
            self.audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.EMAIL_SINGLE_MESSAGE_APPROVAL_REQUESTED.value, resource_type="email_single_message_test", resource_id=execution.id, details={"provider_execution_id": str(execution.id), "approval_request_id": str(approval.id), "message_digest": preview.payload_digest, "simulation_only": preview.simulation_only, "live_send_available": preview.live_send_available})
            self.session.commit()
            return SingleMessageApprovalResponse(**preview.model_dump(), provider_execution_id=execution.id, approval_request_id=approval.id, status=execution.status)
        except IntegrityError as exc:
            self.session.rollback()
            raise EmailConflictError from exc
        except Exception:
            self.session.rollback()
            raise

    def list_single_message_approvals(self, *, company_id: UUID, actor: Administrator, status: str | None, limit: int, offset: int) -> SingleMessageApprovalReviewList:
        statement = select(ApprovalRequest).where(
            ApprovalRequest.company_id == company_id,
            ApprovalRequest.action_type == "provider.execute.generic_smtp_imap.send_email",
            ApprovalRequest.target_resource_type == "provider_execution",
        )
        if status is not None:
            statement = statement.where(ApprovalRequest.status == status)
        statement = statement.order_by(ApprovalRequest.created_at.desc(), ApprovalRequest.id.desc()).limit(limit).offset(offset)
        requests = list(self.session.scalars(statement).all())
        count_statement = select(func.count()).select_from(ApprovalRequest).where(
            ApprovalRequest.company_id == company_id,
            ApprovalRequest.action_type == "provider.execute.generic_smtp_imap.send_email",
            ApprovalRequest.target_resource_type == "provider_execution",
        )
        if status is not None:
            count_statement = count_statement.where(ApprovalRequest.status == status)
        total = int(self.session.scalar(count_statement) or 0)
        items: list[SingleMessageApprovalReview] = []
        for request in requests:
            if request.target_resource_id is None:
                continue
            execution = self.executions.get(company_id, request.target_resource_id)
            if execution is None:
                continue
            payload = execution.request_payload or {}
            if payload.get("payload_schema") != SINGLE_MESSAGE_SCHEMA:
                continue
            try:
                mode = SingleMessageMode(str(payload.get("mode") or SingleMessageMode.SIMULATION.value))
            except ValueError:
                mode = SingleMessageMode.SIMULATION
            items.append(SingleMessageApprovalReview(
                id=request.id,
                provider_execution_id=execution.id,
                requester_administrator_id=request.requester_administrator_id,
                status=request.status,
                requested_action=request.action_type,
                mode=mode,
                sender_email=str(payload.get("sender_email") or ""),
                recipient_email=str(payload.get("recipient_email") or ""),
                subject=str(payload.get("subject") or ""),
                body=str(payload.get("body") or ""),
                payload_digest=str(payload.get("payload_digest") or ""),
                idempotency_key=execution.idempotency_key,
                created_at=request.created_at,
                decision_due_at=request.decision_due_at,
                self_approval_blocked=request.requester_administrator_id == actor.id,
            ))
        return SingleMessageApprovalReviewList(items=items, total=total, limit=limit, offset=offset)

    def execute_single_message_simulation(self, *, company_id: UUID, data: SingleMessageSimulationRequest, actor: Administrator) -> SingleMessageSimulationResponse:
        execution = self.executions.get(company_id, data.provider_execution_id, lock=True)
        if execution is None or execution.provider_key != "generic_smtp_imap" or execution.operation_key != "send_email":
            raise EmailNotFoundError
        if execution.requested_by_administrator_id != actor.id:
            raise EmailForbiddenError
        payload = execution.request_payload or {}
        if payload.get("payload_schema") != SINGLE_MESSAGE_SCHEMA or not payload.get("payload_digest"):
            raise EmailConflictError
        connection = self.connections.connection(company_id=company_id, connection_id=execution.provider_connection_id, for_update=True)
        if connection is None or connection.provider_key != "generic_smtp_imap" or connection.status != "active":
            self._reject_single_message(company_id, actor, "mailbox_not_active", execution.id)
        action = AuthorizationAction(company_id=company_id, actor_type="administrator", actor_administrator_id=actor.id, action_type="provider.execute.generic_smtp_imap.send_email", tool_identifier="provider.generic_smtp_imap.send_email", risk_level=RiskLevel.HIGH, scope_type="company", scope_id=company_id, target_resource_type="provider_execution", target_resource_id=execution.id, provider_connection_id=execution.provider_connection_id)
        authorizer = AuthorizationEvaluatorService(self.approvals, self.authorizations, self.audit, self.session)
        try:
            decision_result = authorizer.evaluate(action)
            if decision_result.status != "authorized" or decision_result.policy_id is None:
                self._reject_single_message(company_id, actor, "approval_required", execution.id)
            usage = authorizer.reserve(ReservationCreate(action=action, policy_id=decision_result.policy_id, reservation_key=execution.id, execution_id=execution.id, reservation_expires_at=datetime.now(UTC) + timedelta(minutes=5)), commit=False)
        except AuthorizationDeniedError as exc:
            self.session.rollback()
            self._reject_single_message(company_id, actor, str(exc.args[0] if exc.args else "approval_required"), execution.id)
        now = datetime.now(UTC)
        execution.status = "running"
        execution.authorization_reference = decision_result.policy_id
        execution.started_at = now
        attempt = ProviderExecutionAttempt(company_id=company_id, provider_execution_id=execution.id, attempt_number=1, status="running", adapter_name=DryRunProviderAdapter.name, request_metadata={"payload_schema": SINGLE_MESSAGE_SCHEMA}, response_metadata={}, error_metadata={}, started_at=now)
        self.executions.add_attempt(attempt)
        self.audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.PROVIDER_EXECUTION_AUTHORIZED.value, resource_type="provider_execution", resource_id=execution.id, details={"policy_id": str(decision_result.policy_id), "usage_id": str(usage.id), "operation_key": "send_email", "simulation_only": True})
        self.audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.PROVIDER_EXECUTION_STARTED.value, resource_type="provider_execution", resource_id=execution.id, details={"operation_key": "send_email", "attempt_number": 1, "simulation_only": True})
        result_metadata = DryRunProviderAdapter().execute(provider_operation_registry.require("generic_smtp_imap", "send_email"), payload, idempotency_key=execution.idempotency_key)
        result_metadata["external_action_taken"] = False
        result_metadata["live_send_available"] = False
        result_metadata["payload_digest"] = payload["payload_digest"]
        completed = datetime.now(UTC)
        execution.status = "succeeded"
        execution.completed_at = completed
        execution.result_metadata = result_metadata
        attempt.status = "succeeded"
        attempt.completed_at = completed
        attempt.response_metadata = {"simulation_only": True, "external_action_taken": False}
        authorizer.transition(company_id=company_id, usage_id=usage.id, status="succeeded", actor_administrator_id=actor.id, commit=False)
        self.audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.PROVIDER_EXECUTION_SUCCEEDED.value, resource_type="provider_execution", resource_id=execution.id, details={"operation_key": "send_email", "simulation_only": True})
        self.audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.EMAIL_SINGLE_MESSAGE_SIMULATED.value, resource_type="email_single_message_test", resource_id=execution.id, details={"provider_execution_id": str(execution.id), "message_digest": payload["payload_digest"], "simulation_only": True})
        self.session.commit()
        return SingleMessageSimulationResponse(provider_execution_id=execution.id, status=execution.status, result_metadata=result_metadata, simulation_only=True, external_action_taken=False)

    def _authorized_single_message_usage(self, *, company_id: UUID, execution: ProviderExecution, actor: Administrator):
        action = AuthorizationAction(company_id=company_id, actor_type="administrator", actor_administrator_id=actor.id, action_type="provider.execute.generic_smtp_imap.send_email", tool_identifier="provider.generic_smtp_imap.send_email", risk_level=RiskLevel.HIGH, scope_type="company", scope_id=company_id, target_resource_type="provider_execution", target_resource_id=execution.id, provider_connection_id=execution.provider_connection_id)
        authorizer = AuthorizationEvaluatorService(self.approvals, self.authorizations, self.audit, self.session)
        decision_result = authorizer.evaluate(action)
        if decision_result.status != "authorized" or decision_result.policy_id is None:
            self._reject_single_message(company_id, actor, "approval_required", execution.id)
        usage = authorizer.reserve(ReservationCreate(action=action, policy_id=decision_result.policy_id, reservation_key=execution.id, execution_id=execution.id, reservation_expires_at=datetime.now(UTC) + timedelta(minutes=5)), commit=False)
        return authorizer, decision_result, usage

    def execute_single_message_live(self, *, company_id: UUID, data: SingleMessageLiveExecutionRequest, actor: Administrator) -> SingleMessageLiveExecutionResponse:
        execution = self.executions.get(company_id, data.provider_execution_id, lock=True)
        if execution is None or execution.provider_key != "generic_smtp_imap" or execution.operation_key != "send_email":
            raise EmailNotFoundError
        if execution.execution_mode != ExecutionMode.LIVE.value:
            raise EmailConflictError
        if execution.requested_by_administrator_id != actor.id:
            raise EmailForbiddenError
        if execution.status in {"succeeded", "failed_before_send", "outcome_uncertain", "failed", "cancelled", "denied", "running"}:
            raise EmailConflictError
        payload = execution.request_payload or {}
        if payload.get("payload_schema") != SINGLE_MESSAGE_SCHEMA or payload.get("mode") != SingleMessageMode.LIVE_TEST.value:
            raise EmailConflictError
        connection, sender_email = self._mailbox_sender(company_id=company_id, provider_connection_id=execution.provider_connection_id, actor=actor)
        recipient_email = str(payload.get("recipient_email") or "")
        subject = str(payload.get("subject") or "")
        if data.subject != subject:
            raise EmailConflictError
        preview_digest = single_message_digest(provider_connection_id=connection.id, sender_email=sender_email, recipient_email=recipient_email, subject=data.subject, body=data.body)
        if preview_digest != payload.get("payload_digest"):
            raise EmailForbiddenError
        self._enforce_single_message_policy(company_id=company_id, actor=actor, sender_email=sender_email, data=SingleMessagePreviewRequest(provider_connection_id=connection.id, recipient_email=recipient_email, subject=data.subject, body=data.body, idempotency_key=execution.idempotency_key, mode=SingleMessageMode.LIVE_TEST))
        credential = self.connections.active_credential(company_id=company_id, connection_id=connection.id, for_update=True)
        if credential is None:
            self._reject_single_message(company_id, actor, "credential_not_active", execution.id)
        if self.encryption is None:
            self._reject_single_message(company_id, actor, "credential_decryption_unavailable", execution.id)
        try:
            authorizer, decision_result, usage = self._authorized_single_message_usage(company_id=company_id, execution=execution, actor=actor)
        except AuthorizationDeniedError as exc:
            self.session.rollback()
            self._reject_single_message(company_id, actor, str(exc.args[0] if exc.args else "approval_required"), execution.id)
        now = datetime.now(UTC)
        execution.status = "running"
        execution.authorization_reference = decision_result.policy_id
        execution.started_at = now
        attempt = ProviderExecutionAttempt(company_id=company_id, provider_execution_id=execution.id, attempt_number=1, status="running", adapter_name=self.smtp_live_transport.name, request_metadata={"payload_schema": SINGLE_MESSAGE_SCHEMA, "message_digest": preview_digest}, response_metadata={}, error_metadata={}, started_at=now)
        self.executions.add_attempt(attempt)
        self.audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.PROVIDER_EXECUTION_AUTHORIZED.value, resource_type="provider_execution", resource_id=execution.id, details={"policy_id": str(decision_result.policy_id), "usage_id": str(usage.id), "operation_key": "send_email", "live_send_available": True})
        self.audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.PROVIDER_EXECUTION_STARTED.value, resource_type="provider_execution", resource_id=execution.id, details={"operation_key": "send_email", "attempt_number": 1, "live_send_available": True})
        self.session.flush()
        password = ""
        try:
            secrets = self.encryption.decrypt(
                credential.encrypted_payload,
                credential.nonce,
                company_id=company_id,
                connection_id=connection.id,
                credential_id=credential.id,
                provider_key=connection.provider_key,
                encryption_version=credential.encryption_version,
                encryption_key_id=credential.encryption_key_id,
            ).secrets
            password = str(secrets.get("password") or "")
            result: MailboxSendResult = self.smtp_live_transport.send_email(configuration=connection.configuration, password=password, sender_email=sender_email, recipient_email=recipient_email, subject=data.subject, body=data.body, timeout_seconds=15)
            completed = datetime.now(UTC)
            execution.status = "succeeded"
            execution.completed_at = completed
            execution.result_metadata = {"smtp_status": "accepted", "server_response": result.server_response, "message_digest": preview_digest, "external_action_taken": True, "delivery_claimed": False}
            attempt.status = "succeeded"
            attempt.completed_at = completed
            attempt.response_metadata = {"smtp_status": "accepted", "server_response": result.server_response}
            authorizer.transition(company_id=company_id, usage_id=usage.id, status="succeeded", actor_administrator_id=actor.id, commit=False)
            self.audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.PROVIDER_EXECUTION_SUCCEEDED.value, resource_type="provider_execution", resource_id=execution.id, details={"operation_key": "send_email", "status": "smtp_accepted", "message_digest": preview_digest, "live_send_available": True})
            self.session.commit()
            return SingleMessageLiveExecutionResponse(provider_execution_id=execution.id, status=execution.status, result_metadata=execution.result_metadata, simulation_only=False, external_action_taken=True)
        except MailboxSendOutcomeUncertainError as exc:
            status_value = "outcome_uncertain"
            category = exc.safe_category
            external_action = True
        except MailboxSendError as exc:
            status_value = "failed_before_send"
            category = exc.safe_category
            external_action = False
        except Exception:
            status_value = "outcome_uncertain"
            category = "outcome_uncertain"
            external_action = True
        finally:
            password = ""
        completed = datetime.now(UTC)
        execution.status = status_value
        execution.completed_at = completed
        execution.error_category = category
        execution.error_message = "SMTP live send did not complete successfully."
        execution.result_metadata = {"smtp_status": status_value, "message_digest": preview_digest, "external_action_taken": external_action, "delivery_claimed": False}
        attempt.status = status_value
        attempt.completed_at = completed
        attempt.error_metadata = {"category": category}
        authorizer.transition(company_id=company_id, usage_id=usage.id, status="failed", actor_administrator_id=actor.id, failure_code=category, commit=False)
        self.audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.PROVIDER_EXECUTION_FAILED.value, resource_type="provider_execution", resource_id=execution.id, details={"operation_key": "send_email", "status": status_value, "category": category, "message_digest": preview_digest, "live_send_available": True})
        self.session.commit()
        return SingleMessageLiveExecutionResponse(provider_execution_id=execution.id, status=execution.status, result_metadata=execution.result_metadata, simulation_only=False, external_action_taken=external_action)

    def _reject_sandbox(self, company_id: UUID, actor: Administrator, proposal: EmailReplyProposal, reason_code: str) -> None:
        self._event(
            company_id,
            actor,
            AuditAction.PROVIDER_EXECUTION_DENIED,
            "email_reply_proposal",
            proposal.id,
            {
                "operation_key": "send_email",
                "reason_code": reason_code,
                "sandbox": True,
            },
        )
        self.session.commit()
        raise EmailSandboxRejectedError(reason_code)

    def _enforce_sandbox(self, company_id: UUID, proposal: EmailReplyProposal, actor: Administrator) -> None:
        if get_settings().app_environment == "development":
            return
        policy = self._sandbox_policy(company_id)
        if not bool(policy.get("enabled", True)):
            self._reject_sandbox(company_id, actor, proposal, "sandbox_disabled")
        if bool(policy.get("emergency_stop", False)):
            self._reject_sandbox(company_id, actor, proposal, "emergency_stop_enabled")
        recipients = [proposal.recipient_email.casefold()]
        if len(recipients) > int(policy.get("max_recipients_per_message", 1)):
            self._reject_sandbox(company_id, actor, proposal, "too_many_recipients")
        allowed_recipients = {str(item).strip().casefold() for item in policy.get("recipient_allowlist", [])}
        if not allowed_recipients or any(item not in allowed_recipients for item in recipients):
            self._reject_sandbox(company_id, actor, proposal, "recipient_not_allowlisted")
        inbound = self.repo.inbound(company_id, proposal.inbound_email_id)
        sender = inbound.recipient_email.casefold() if inbound else ""
        allowed_senders = {str(item).strip().casefold() for item in policy.get("sender_allowlist", [])}
        if not allowed_senders or sender not in allowed_senders:
            self._reject_sandbox(company_id, actor, proposal, "sender_not_allowlisted")
        prefix = str(policy.get("required_subject_prefix", "")).strip()
        if prefix and not proposal.subject.startswith(prefix):
            self._reject_sandbox(company_id, actor, proposal, "subject_prefix_required")
        if len(proposal.body.encode("utf-8")) > int(policy.get("max_message_bytes", 100_000)):
            self._reject_sandbox(company_id, actor, proposal, "message_too_large")
        if bool(policy.get("attachments_enabled", False)):
            self._reject_sandbox(company_id, actor, proposal, "attachments_not_supported")
        now = datetime.now(UTC)
        if self._sent_count_since(company_id, now - timedelta(hours=1)) >= int(policy.get("max_messages_per_hour", 5)):
            self._reject_sandbox(company_id, actor, proposal, "hourly_quota_exceeded")
        if self._sent_count_since(company_id, now - timedelta(days=1)) >= int(policy.get("max_messages_per_day", 10)):
            self._reject_sandbox(company_id, actor, proposal, "daily_quota_exceeded")

    def import_test(self, company_id: UUID, data: TestInboundEmailImport, actor: Administrator):
        if self.repo.inbound_by_external(company_id, data.external_message_id):
            raise EmailConflictError
        item = InboundEmail(company_id=company_id, provider_connection_id=None, status="received", **data.model_dump())
        try:
            self.repo.add(item)
            self._event(company_id, actor, AuditAction.EMAIL_IMPORTED, "inbound_email", item.id, {"external_message_id": item.external_message_id, "status": item.status})
            self.session.commit()
            return item
        except IntegrityError as exc:
            self.session.rollback()
            raise EmailConflictError from exc

    def _status(self, proposal):
        if proposal is None or proposal.approval_request_id is None:
            return proposal.status if proposal else None, None
        approval = self.approvals.get_request(company_id=proposal.company_id, request_id=proposal.approval_request_id)
        if approval and approval.status == "approved" and proposal.status == "awaiting_approval":
            proposal.status = "approved"
        elif approval and approval.status == "denied" and proposal.status == "awaiting_approval":
            proposal.status = "rejected"
        return proposal.status, approval.status if approval else None

    def summary(self, item):
        proposal = self.repo.proposal_for_inbound(item.company_id, item.id)
        proposal_status, approval_status = self._status(proposal)
        outbound = self.repo.outbound_for_proposal(item.company_id, proposal.id) if proposal else None
        return {
            "id": item.id, "sender_name": item.sender_name, "sender_email": item.sender_email,
            "recipient_email": item.recipient_email, "subject": item.subject, "received_at": item.received_at,
            "status": item.status, "proposal_status": proposal_status, "approval_status": approval_status,
            "send_status": outbound.status if outbound else None,
        }

    def list(self, company_id: UUID, limit: int, offset: int):
        items = self.repo.list_inbound(company_id, limit, offset)
        return [self.summary(item) for item in items], self.repo.count_inbound(company_id)

    def detail(self, company_id: UUID, email_id: UUID):
        item = self.repo.inbound(company_id, email_id)
        if item is None: raise EmailNotFoundError
        result = self.summary(item)
        proposal = self.repo.proposal_for_inbound(company_id, email_id)
        outbound = self.repo.outbound_for_proposal(company_id, proposal.id) if proposal else None
        result.update({"external_message_id": item.external_message_id, "body": item.body, "created_at": item.created_at, "updated_at": item.updated_at, "reply_proposal": proposal, "outbound_email": outbound})
        return result

    def create_proposal(self, company_id: UUID, email_id: UUID, data: ReplyProposalWrite | None, actor: Administrator):
        inbound = self.repo.inbound(company_id, email_id, lock=True)
        if inbound is None: raise EmailNotFoundError
        if self.repo.proposal_for_inbound(company_id, email_id): raise EmailConflictError
        values = data.model_dump() if data else {"recipient_email": inbound.sender_email, "subject": reply_subject(inbound.subject), "body": "Draft reply — replace this text before requesting approval."}
        proposal = EmailReplyProposal(company_id=company_id, inbound_email_id=email_id, status="draft", content_sha256=content_digest(**{"recipient": values["recipient_email"], "subject": values["subject"], "body": values["body"]}), created_by_administrator_id=actor.id, **values)
        self.repo.add(proposal); inbound.status = "reply_drafted"
        self._event(company_id, actor, AuditAction.EMAIL_REPLY_DRAFTED, "email_reply_proposal", proposal.id, {"inbound_email_id": str(email_id), "status": proposal.status})
        self.session.commit(); return proposal

    def update_proposal(self, company_id: UUID, proposal_id: UUID, data: ReplyProposalWrite, actor: Administrator):
        proposal = self.repo.proposal(company_id, proposal_id, lock=True)
        if proposal is None: raise EmailNotFoundError
        if proposal.status != "draft" or proposal.approval_request_id is not None: raise EmailConflictError
        for key, value in data.model_dump().items(): setattr(proposal, key, value)
        proposal.content_sha256 = content_digest(proposal.recipient_email, proposal.subject, proposal.body)
        self._event(company_id, actor, AuditAction.EMAIL_REPLY_UPDATED, "email_reply_proposal", proposal.id, {"status": proposal.status})
        self.session.commit(); return proposal

    def submit(self, company_id: UUID, proposal_id: UUID, actor: Administrator):
        proposal = self.repo.proposal(company_id, proposal_id, lock=True)
        if proposal is None: raise EmailNotFoundError
        if proposal.status != "draft" or proposal.approval_request_id is not None: raise EmailConflictError
        digest = content_digest(proposal.recipient_email, proposal.subject, proposal.body)
        if digest != proposal.content_sha256: raise EmailConflictError
        request = self.approval_service.create_request(company_id=company_id, actor=actor, commit=False, payload=ApprovalRequestCreate(
            authorization_mode=AuthorizationMode.APPROVE_SINGLE_ACTION, action_type="email.reply.send",
            tool_identifier="provider.local_test_email.send_email", risk_level=RiskLevel.HIGH,
            scope_type="company", scope_id=company_id, target_resource_type="email_reply_proposal",
            target_resource_id=proposal.id, requested_conditions=AuthorizationConditionsV1(payload_schema="email_reply.v1", payload_digest=digest),
            reason="Review and approve this exact email reply.",
        ))
        proposal.approval_request_id = request.id; proposal.status = "awaiting_approval"
        inbound = self.repo.inbound(company_id, proposal.inbound_email_id, lock=True); inbound.status = "awaiting_approval"
        self._event(company_id, actor, AuditAction.EMAIL_REPLY_SUBMITTED, "email_reply_proposal", proposal.id, {"approval_request_id": str(request.id), "status": proposal.status})
        self.session.commit(); return proposal

    def list_approvals(self, company_id: UUID, limit: int, offset: int):
        requests = self.approvals.list_requests(company_id=company_id, requester_administrator_id=None, status=None, action_type="email.reply.send", tool_identifier=None, risk_level=None, campaign_id=None, limit=limit, offset=offset)
        items = []
        for request in requests:
            proposal = self.repo.proposal(company_id, request.target_resource_id) if request.target_resource_id else None
            if proposal is None: continue
            inbound = self.repo.inbound(company_id, proposal.inbound_email_id)
            items.append({"id": request.id, "status": request.status, "requester_administrator_id": request.requester_administrator_id, "created_at": request.created_at, "recipient_email": proposal.recipient_email, "subject": proposal.subject, "body": proposal.body, "inbound_email_id": inbound.id, "inbound_subject": inbound.subject, "requested_action": request.action_type})
        total = self.approvals.count_requests(company_id=company_id, requester_administrator_id=None, status=None, action_type="email.reply.send", tool_identifier=None, risk_level=None, campaign_id=None)
        return items, total

    def decide(self, company_id: UUID, request_id: UUID, actor: Administrator, actor_role: str | None, approve: bool):
        request = self.approvals.get_request(company_id=company_id, request_id=request_id)
        if request is None or request.action_type != "email.reply.send" or request.target_resource_id is None:
            raise EmailNotFoundError
        proposal = self.repo.proposal(company_id, request.target_resource_id, lock=True)
        if proposal is None or proposal.approval_request_id != request.id or proposal.status != "awaiting_approval":
            raise EmailConflictError
        try:
            if approve:
                self.approval_service.approve(company_id=company_id, request_id=request_id, actor=actor, actor_role=actor_role, payload=ApprovalDecisionCreate(), commit=False)
                proposal.status = "approved"; inbound_status = "approved"
            else:
                self.approval_service.deny(company_id=company_id, request_id=request_id, actor=actor, actor_role=actor_role, reason=None, commit=False)
                proposal.status = "rejected"; inbound_status = "rejected"
            inbound = self.repo.inbound(company_id, proposal.inbound_email_id, lock=True)
            inbound.status = inbound_status
            self.session.commit()
            return request
        except Exception:
            self.session.rollback()
            raise

    def send(self, company_id: UUID, proposal_id: UUID, data: SendReplyRequest, actor: Administrator):
        proposal = self.repo.proposal(company_id, proposal_id, lock=True)
        if proposal is None: raise EmailNotFoundError
        existing = self.repo.outbound_for_proposal(company_id, proposal_id)
        if existing is not None: return existing
        self._enforce_sandbox(company_id, proposal, actor)
        if proposal.approval_request_id is None: raise EmailForbiddenError
        approval = self.approvals.get_request(company_id=company_id, request_id=proposal.approval_request_id, for_update=True)
        digest = content_digest(proposal.recipient_email, proposal.subject, proposal.body)
        if approval is None or approval.status != "approved" or approval.target_resource_id != proposal.id or approval.requested_conditions.get("payload_digest") != digest or proposal.content_sha256 != digest:
            raise EmailForbiddenError
        connection = self.connections.connection(company_id=company_id, connection_id=data.provider_connection_id, for_update=True)
        if connection is None or connection.provider_key != "local_test_email" or connection.status != "active": raise EmailForbiddenError
        policy = self.approvals.policy_for_request(company_id=company_id, request_id=approval.id)
        if policy is None: raise EmailForbiddenError
        execution = ProviderExecution(company_id=company_id, provider_connection_id=connection.id, provider_key="local_test_email", operation_key="send_email", execution_mode="dry_run", status="running", requested_by_administrator_id=actor.id, authorization_reference=policy.id, idempotency_key=f"email-reply:{proposal.id}", request_payload={"payload_schema": "email_reply.v1", "proposal_id": str(proposal.id), "payload_digest": digest, "controlled_failure": data.controlled_failure}, result_metadata={}, started_at=datetime.now(UTC))
        self.executions.add(execution)
        attempt = ProviderExecutionAttempt(company_id=company_id, provider_execution_id=execution.id, attempt_number=1, status="running", adapter_name=LocalTestEmailAdapter.name, request_metadata={"payload_schema": "email_reply.v1"}, response_metadata={}, error_metadata={}, started_at=execution.started_at)
        self.executions.add_attempt(attempt)
        outbound = OutboundEmail(company_id=company_id, reply_proposal_id=proposal.id, provider_execution_id=execution.id, recipient_email=proposal.recipient_email, subject=proposal.subject, body=proposal.body, content_sha256=digest, status="pending")
        self.repo.add(outbound)
        self._event(company_id, actor, AuditAction.PROVIDER_EXECUTION_REQUESTED, "provider_execution", execution.id, {"provider_key": "local_test_email", "operation_key": "send_email", "execution_mode": "dry_run"})
        self._event(company_id, actor, AuditAction.PROVIDER_EXECUTION_AUTHORIZED, "provider_execution", execution.id, {"policy_id": str(policy.id), "operation_key": "send_email"})
        self._event(company_id, actor, AuditAction.PROVIDER_EXECUTION_STARTED, "provider_execution", execution.id, {"operation_key": "send_email", "attempt_number": 1})
        try:
            result = LocalTestEmailAdapter().execute(provider_operation_registry.require("local_test_email", "send_email"), {"recipient_email": proposal.recipient_email, "subject": proposal.subject, "body": proposal.body, "controlled_failure": data.controlled_failure}, idempotency_key=execution.idempotency_key)
            now = datetime.now(UTC); execution.status = "succeeded"; execution.result_metadata = result; execution.completed_at = now
            attempt.status = "succeeded"; attempt.response_metadata = {"provider_message_id": result["provider_message_id"]}; attempt.completed_at = now
            outbound.status = "sent"; outbound.provider_message_id = result["provider_message_id"]; outbound.sent_at = now
            proposal.status = "sent"; inbound = self.repo.inbound(company_id, proposal.inbound_email_id, lock=True); inbound.status = "sent"
            self._event(company_id, actor, AuditAction.PROVIDER_EXECUTION_SUCCEEDED, "provider_execution", execution.id, {"operation_key": "send_email"})
            self._event(company_id, actor, AuditAction.EMAIL_REPLY_SENT, "outbound_email", outbound.id, {"provider_execution_id": str(execution.id), "status": "sent"})
            self.session.commit(); return outbound
        except Exception as exc:
            now = datetime.now(UTC); execution.status = "failed"; execution.error_category = "provider_error"; execution.error_message = "Test delivery failed."; execution.completed_at = now
            attempt.status = "failed"; attempt.error_metadata = {"category": "provider_error"}; attempt.completed_at = now
            outbound.status = "failed"; proposal.status = "send_failed"; inbound = self.repo.inbound(company_id, proposal.inbound_email_id, lock=True); inbound.status = "send_failed"
            self._event(company_id, actor, AuditAction.PROVIDER_EXECUTION_FAILED, "provider_execution", execution.id, {"operation_key": "send_email", "category": "provider_error"})
            self._event(company_id, actor, AuditAction.EMAIL_REPLY_SEND_FAILED, "outbound_email", outbound.id, {"provider_execution_id": str(execution.id), "status": "failed"})
            self.session.commit()
            raise EmailConflictError from exc


def get_email_workflow_service(request: Request, session: Annotated[Session, Depends(get_db_session)]) -> EmailWorkflowService:
    keyring = request.app.state.credential_encryption_keyring
    return EmailWorkflowService(session, CredentialEncryptionService(keyring))
