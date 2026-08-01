"""Preview-only Agent Manager built on Agent Identity and Approval Manager."""

from datetime import UTC, datetime
from typing import Annotated, Any, Protocol
from uuid import UUID

from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import RiskLevel
from app.db.session import get_db_session
from app.models.administrator import Administrator
from app.models.agent import Agent
from app.models.audit_log import AuditAction
from app.repositories.agent import AgentRepository
from app.repositories.approval import ApprovalRepository, AuthorizationRepository
from app.repositories.audit_log import AuditLogRepository
from app.schemas.agent_manager import (
    AgentAuthorizationResult,
    AgentManagerAgentResponse,
    AgentManagerCreateFromTemplateRequest,
    AgentManagerInstructionsUpdate,
    AgentManagerListResponse,
    AgentManagerTemplateResponse,
    AgentPreviewTaskRequest,
    AgentPreviewTaskResponse,
    AgentPromptPreviewResponse,
    AgentProposalResponse,
    SAFE_EMAIL_PREVIEW_TEMPLATE_ID,
)
from app.schemas.approval import AuthorizationAction
from app.services.audit_log import AuditLogService
from app.services.authorization_evaluator import AuthorizationEvaluatorService


AGENT_MANAGER_METADATA_KEY = "agent_manager"
EMAIL_PREVIEW_TOOLS = [
    "email.schedule.preview",
    "email.campaigns.list",
    "email.reply.synthetic.classify",
    "email.reply.synthetic.draft",
    "email.campaign.pause.propose",
]
EMAIL_PREVIEW_PERMISSIONS = [
    "agent.preview.email_schedule",
    "agent.draft.synthetic_reply",
    "agent.classify.synthetic_reply",
    "agent.propose.campaign_pause",
]
FORBIDDEN_ACTIONS = [
    "email.message.send",
    "external.bulk_communication",
    "credential.read",
    "database.direct_access",
    "shell.execute",
    "docker.socket.access",
]


class AgentManagerNotFoundError(Exception):
    pass


class AgentManagerConflictError(Exception):
    pass


class AgentManagerDeniedError(Exception):
    pass


class AgentManagerPayloadError(Exception):
    pass


class PreviewRuntimeUnavailableError(Exception):
    pass


class PreviewRuntimeOutputError(Exception):
    pass


class PreviewRuntime(Protocol):
    def run(self, *, task: AgentPreviewTaskRequest) -> AgentProposalResponse: ...


def email_preview_template() -> AgentManagerTemplateResponse:
    return AgentManagerTemplateResponse(
        template_id=SAFE_EMAIL_PREVIEW_TEMPLATE_ID,
        name="Email Operations Preview Agent",
        role="Email operations preview analyst",
        runtime_type="local_preview",
        approval_mode="always_require_approval",
        allowed_tools=EMAIL_PREVIEW_TOOLS,
        forbidden_actions=FORBIDDEN_ACTIONS,
        default_permissions=EMAIL_PREVIEW_PERMISSIONS,
    )


class DeterministicEmailPreviewRuntime:
    """Synthetic local adapter. It never calls providers or external networks."""

    def run(self, *, task: AgentPreviewTaskRequest) -> AgentProposalResponse:
        if task.task_key == "preview_next_email_actions":
            return AgentProposalResponse(
                proposal_type="schedule_preview",
                summary="Preview the next 10 scheduled email actions using stored non-secret schedule policy.",
                recommended_action="Open Email Operations and review dry-run scheduler output before any live worker exists.",
                safety_notes=["No email is sent.", "No mailbox credential is read.", "No provider execution is created."],
            )
        if task.task_key == "draft_interested_follow_up":
            return AgentProposalResponse(
                proposal_type="draft_reply",
                summary="Synthetic interested reply indicates a polite follow-up draft is appropriate.",
                recommended_action="Create a draft only and route any send through explicit approval.",
                draft_subject="Re: Thanks for your interest",
                draft_body="Thanks for the reply. I can share a short overview and suggest a time to discuss next steps.",
                safety_notes=["Draft only.", "Synthetic input only.", "Approval required before any send."],
            )
        if task.task_key == "classify_unsubscribe":
            return AgentProposalResponse(
                proposal_type="classification",
                summary="Synthetic reply requests no further contact.",
                recommended_action="Suppress future contact and do not schedule follow-ups.",
                classification="unsubscribe",
                safety_notes=["No further contact recommended.", "No mailbox mutation performed."],
            )
        if task.task_key == "propose_campaign_pause":
            return AgentProposalResponse(
                proposal_type="pause_campaign",
                summary="Synthetic conditions justify pausing the campaign before further outreach.",
                recommended_action="Request approval to pause the campaign schedule.",
                safety_notes=["Proposal only.", "Approval Manager evaluation is required."],
            )
        if task.task_key == "attempt_forbidden_send":
            return AgentProposalResponse(
                proposal_type="forbidden_send",
                summary="The requested send action is forbidden for this preview agent.",
                recommended_action="Deny the send and keep all output in preview mode.",
                safety_notes=["No send is allowed.", "No recipient list accepted.", "No provider execution created."],
            )
        raise PreviewRuntimeOutputError


class AgentManagerService:
    def __init__(
        self,
        *,
        agents: AgentRepository,
        audit: AuditLogService,
        authorizer: AuthorizationEvaluatorService,
        session: Session,
        runtime: PreviewRuntime | None = None,
    ) -> None:
        self._agents = agents
        self._audit = audit
        self._authorizer = authorizer
        self._session = session
        self._runtime = runtime or DeterministicEmailPreviewRuntime()

    def templates(self) -> list[AgentManagerTemplateResponse]:
        return [email_preview_template()]

    def list_agents(self, *, company_id: UUID, limit: int, offset: int) -> AgentManagerListResponse:
        total_agents = self._agents.count_agents(company_id=company_id, status=None, agent_type=None, search=None)
        all_agents = self._agents.list_agents(company_id=company_id, status=None, agent_type=None, search=None, limit=max(total_agents, 1), offset=0)
        managed = [self._response(item) for item in all_agents if self._metadata(item)]
        return AgentManagerListResponse(items=managed[offset : offset + limit], total=len(managed), limit=limit, offset=offset)

    def create_from_template(self, *, company_id: UUID, data: AgentManagerCreateFromTemplateRequest, actor: Administrator) -> AgentManagerAgentResponse:
        if data.template_id != SAFE_EMAIL_PREVIEW_TEMPLATE_ID:
            raise AgentManagerNotFoundError
        existing = self._agents.get_by_slug(company_id=company_id, slug=SAFE_EMAIL_PREVIEW_TEMPLATE_ID.replace("_", "-"))
        if existing is not None:
            return self._response(existing)
        metadata = self._template_metadata(company_instructions=data.company_instructions)
        try:
            agent = self._agents.create_agent(
                company_id=company_id,
                name=data.name or "Email Operations Preview Agent",
                slug="email-operations-preview-agent",
                agent_type="email_outreach",
                description="Preview-only email operations agent for synthetic tasks.",
                status="inactive",
                is_system=False,
                metadata_=metadata,
                created_by_administrator_id=actor.id,
            )
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.AGENT_CREATED.value, resource_type="agent", resource_id=agent.id, details={"agent_type": agent.agent_type, "status": agent.status, "runtime_type": "local_preview"})
            for permission in EMAIL_PREVIEW_PERMISSIONS:
                self._agents.create_permission(company_id=company_id, agent_id=agent.id, permission_key=permission, granted_by_administrator_id=actor.id, grant_reason="Email preview template default permission.")
                self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.AGENT_PERMISSION_GRANTED.value, resource_type="agent_permission", resource_id=None, details={"agent_id": str(agent.id), "permission_key": permission})
            self._session.commit()
            return self._response(agent)
        except IntegrityError as exc:
            self._session.rollback()
            raise AgentManagerConflictError from exc
        except Exception:
            self._session.rollback()
            raise

    def update_instructions(self, *, company_id: UUID, agent_id: UUID, data: AgentManagerInstructionsUpdate, actor: Administrator) -> AgentManagerAgentResponse:
        agent = self._get(company_id=company_id, agent_id=agent_id, for_update=True)
        metadata = dict(agent.metadata_ or {})
        managed = dict(metadata.get(AGENT_MANAGER_METADATA_KEY) or {})
        instructions = dict(managed.get("instructions") or {})
        instructions["company_instructions"] = data.company_instructions
        managed["instructions"] = instructions
        metadata[AGENT_MANAGER_METADATA_KEY] = managed
        agent.metadata_ = metadata
        agent.updated_by_administrator_id = actor.id
        try:
            self._agents.save_agent(agent)
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=AuditAction.AGENT_UPDATED.value, resource_type="agent", resource_id=agent.id, details={"changed": True, "operation": "instructions_updated"})
            self._session.commit()
            return self._response(agent)
        except Exception:
            self._session.rollback()
            raise

    def set_active(self, *, company_id: UUID, agent_id: UUID, active: bool, actor: Administrator) -> AgentManagerAgentResponse:
        agent = self._get(company_id=company_id, agent_id=agent_id, for_update=True)
        if agent.status == "revoked":
            raise AgentManagerConflictError
        previous = agent.status
        agent.status = "active" if active else "inactive"
        agent.auth_version += 1
        agent.updated_by_administrator_id = actor.id
        action = AuditAction.AGENT_ACTIVATED if active else AuditAction.AGENT_DEACTIVATED
        try:
            self._agents.save_agent(agent)
            self._audit.append_company_event(company_id=company_id, actor_administrator_id=actor.id, action=action.value, resource_type="agent", resource_id=agent.id, details={"previous_status": previous, "new_status": agent.status, "changed": previous != agent.status})
            self._session.commit()
            return self._response(agent)
        except Exception:
            self._session.rollback()
            raise

    def prompt_preview(self, *, company_id: UUID, agent_id: UUID) -> AgentPromptPreviewResponse:
        agent = self._get(company_id=company_id, agent_id=agent_id)
        sections = self._prompt_sections(agent)
        return AgentPromptPreviewResponse(
            agent_id=agent.id,
            template_id=SAFE_EMAIL_PREVIEW_TEMPLATE_ID,
            sections=sections,
            prompt_text="\n\n".join(f"{key.upper()}\n{value}" for key, value in sections.items()),
        )

    def run_task(self, *, company_id: UUID, agent_id: UUID, data: AgentPreviewTaskRequest, actor: Administrator) -> AgentPreviewTaskResponse:
        agent = self._get(company_id=company_id, agent_id=agent_id)
        if agent.status != "active":
            raise AgentManagerDeniedError
        if len((data.synthetic_reply or "").encode()) > 4096:
            raise AgentManagerPayloadError
        proposal = self._runtime.run(task=data)
        if not isinstance(proposal, AgentProposalResponse):
            raise PreviewRuntimeOutputError
        authorization = self._authorization(company_id=company_id, agent=agent, task_key=data.task_key)
        status = "denied" if data.task_key == "attempt_forbidden_send" else "previewed"
        action = AuditAction.AGENT_MANAGER_TASK_DENIED if status == "denied" else AuditAction.AGENT_MANAGER_TASK_PREVIEWED
        try:
            event = self._audit.append_company_event(
                company_id=company_id,
                actor_administrator_id=actor.id,
                action=action.value,
                resource_type="agent_manager",
                resource_id=agent.id,
                details={
                    "task_key": data.task_key,
                    "proposal_type": proposal.proposal_type,
                    "authorization_status": authorization.status,
                    "runtime_type": "local_preview",
                    "denied_reason": "forbidden_send" if status == "denied" else None,
                    "dry_run": True,
                },
            )
            metadata = dict(agent.metadata_ or {})
            managed = dict(metadata.get(AGENT_MANAGER_METADATA_KEY) or {})
            managed["last_activity_at"] = event.created_at.isoformat()
            metadata[AGENT_MANAGER_METADATA_KEY] = managed
            agent.metadata_ = metadata
            self._agents.save_agent(agent)
            self._session.commit()
            return AgentPreviewTaskResponse(
                agent_id=agent.id,
                task_key=data.task_key,
                runtime_type="local_preview",
                status=status,
                proposal=proposal,
                authorization=authorization,
                audit_event_id=event.id,
            )
        except Exception:
            self._session.rollback()
            raise

    def _authorization(self, *, company_id: UUID, agent: Agent, task_key: str) -> AgentAuthorizationResult:
        if task_key == "attempt_forbidden_send":
            return AgentAuthorizationResult(status="blocked", reason_code="forbidden_by_agent_template", effective_risk=RiskLevel.HIGH.value)
        action_type = "metadata.read" if task_key in {"preview_next_email_actions", "draft_interested_follow_up", "classify_unsubscribe"} else "email.campaign.pause"
        risk = RiskLevel.LOW if action_type == "metadata.read" else RiskLevel.HIGH
        result = self._authorizer.evaluate(
            AuthorizationAction(
                company_id=company_id,
                actor_type="agent",
                actor_agent_id=agent.id,
                action_type=action_type,
                tool_identifier=f"agent_manager.{task_key}",
                risk_level=risk,
                scope_type="agent_task",
                scope_id=agent.id,
            )
        )
        return AgentAuthorizationResult(status=result.status, reason_code=result.reason_code, effective_risk=result.effective_risk.value, approval_request_id=result.approval_request_id, policy_id=result.policy_id)

    def _get(self, *, company_id: UUID, agent_id: UUID, for_update: bool = False) -> Agent:
        agent = self._agents.get_agent(company_id=company_id, agent_id=agent_id, for_update=for_update)
        if agent is None or not self._metadata(agent):
            raise AgentManagerNotFoundError
        return agent

    def _metadata(self, agent: Agent) -> dict[str, Any]:
        value = (agent.metadata_ or {}).get(AGENT_MANAGER_METADATA_KEY)
        return value if isinstance(value, dict) and value.get("template_id") == SAFE_EMAIL_PREVIEW_TEMPLATE_ID else {}

    def _template_metadata(self, *, company_instructions: str) -> dict[str, Any]:
        return {
            AGENT_MANAGER_METADATA_KEY: {
                "template_id": SAFE_EMAIL_PREVIEW_TEMPLATE_ID,
                "role": "Email operations preview analyst",
                "runtime_type": "local_preview",
                "approval_mode": "always_require_approval",
                "assigned_tools": EMAIL_PREVIEW_TOOLS,
                "health": "ready",
                "readiness": "preview_only",
                "last_activity_at": None,
                "instructions": {
                    "system_identity": "CompanyAI controlled preview agent.",
                    "company_scope": "Use only the active CompanyAI company context supplied by the API.",
                    "role": "Inspect safe email campaign and mailbox metadata and prepare preview-only recommendations.",
                    "objectives": ["Preview scheduler actions.", "Draft synthetic replies.", "Classify synthetic replies.", "Propose pauses."],
                    "allowed_tools": EMAIL_PREVIEW_TOOLS,
                    "forbidden_actions": FORBIDDEN_ACTIONS,
                    "approval_rules": "Any external action requires CompanyAI Approval Manager and is not executable by this preview runtime.",
                    "company_instructions": company_instructions,
                    "output_schema": "AgentPreviewTaskResponse.v1",
                    "escalation_rules": "Stop for credentials, real sends, paid APIs, phone calls or campaign launch.",
                },
            }
        }

    def _prompt_sections(self, agent: Agent) -> dict[str, Any]:
        return dict(self._metadata(agent).get("instructions") or {})

    def _response(self, agent: Agent) -> AgentManagerAgentResponse:
        metadata = self._metadata(agent)
        permissions = [item.permission_key for item in self._agents.list_permissions(company_id=agent.company_id, agent_id=agent.id, active_only=True)]
        last_activity = metadata.get("last_activity_at")
        parsed_last_activity = datetime.fromisoformat(last_activity) if isinstance(last_activity, str) else None
        return AgentManagerAgentResponse(
            id=agent.id,
            company_id=agent.company_id,
            name=agent.name,
            slug=agent.slug,
            role=str(metadata.get("role") or "Preview agent"),
            status=agent.status,
            runtime_type=str(metadata.get("runtime_type") or "local_preview"),
            assigned_tools=list(metadata.get("assigned_tools") or []),
            permissions=permissions,
            approval_mode=str(metadata.get("approval_mode") or "always_require_approval"),
            health=str(metadata.get("health") or "ready"),
            readiness=str(metadata.get("readiness") or "preview_only"),
            last_activity_at=parsed_last_activity,
            instructions=dict(metadata.get("instructions") or {}),
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )


def get_agent_manager_service(session: Annotated[Session, Depends(get_db_session)]) -> AgentManagerService:
    audit = AuditLogService(AuditLogRepository(session))
    return AgentManagerService(
        agents=AgentRepository(session),
        audit=audit,
        authorizer=AuthorizationEvaluatorService(ApprovalRepository(session), AuthorizationRepository(session), audit, session),
        session=session,
    )
