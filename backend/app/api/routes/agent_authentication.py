"""Internal endpoints for machine credential exchange and agent identity."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies.agent_authentication import agent_authentication_required, require_current_agent, require_raw_agent_credential
from app.schemas.agent import AgentResponse, AgentTokenResponse, AuthenticatedAgentResponse
from app.services.agent_identity import AuthenticatedAgent, AgentIdentityService, InvalidAgentAuthenticationError, get_agent_identity_service

router = APIRouter(prefix="/internal/agent-auth", tags=["internal-agent-auth"])


@router.post("/token", response_model=AgentTokenResponse)
def exchange_agent_credential(raw: Annotated[str, Depends(require_raw_agent_credential)], service: Annotated[AgentIdentityService, Depends(get_agent_identity_service)]) -> AgentTokenResponse:
    try: issued = service.exchange_credential(raw)
    except InvalidAgentAuthenticationError as exc: raise agent_authentication_required() from exc
    return AgentTokenResponse(access_token=issued.access_token, expires_in=issued.expires_in, agent=AgentResponse.model_validate(issued.agent), company_id=issued.agent.company_id, credential_id=issued.credential.id)


@router.get("/me", response_model=AuthenticatedAgentResponse)
def get_agent_identity(identity: Annotated[AuthenticatedAgent, Depends(require_current_agent)]) -> AuthenticatedAgentResponse:
    agent = identity.agent
    return AuthenticatedAgentResponse(agent_id=agent.id, company_id=agent.company_id, name=agent.name, slug=agent.slug, agent_type=agent.agent_type, status=agent.status, permissions=list(identity.permissions), credential_id=identity.credential.id)
