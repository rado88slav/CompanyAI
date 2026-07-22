"""Internal machine authentication dependencies, separate from administrators."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.schemas.approval import AuthorizationAction
from app.services.agent_identity import AuthenticatedAgent, AgentIdentityService, InvalidAgentAuthenticationError, get_agent_identity_service

_agent_bearer = HTTPBearer(auto_error=False)


def agent_authentication_required() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Valid agent authentication is required.", headers={"WWW-Authenticate": "Bearer"})


def require_raw_agent_credential(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_agent_bearer)]) -> str:
    if credentials is None or credentials.scheme.lower() != "agentcredential" or not credentials.credentials: raise agent_authentication_required()
    return credentials.credentials


def require_current_agent(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_agent_bearer)], service: Annotated[AgentIdentityService, Depends(get_agent_identity_service)]) -> AuthenticatedAgent:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials: raise agent_authentication_required()
    try: return service.resolve_token(credentials.credentials)
    except InvalidAgentAuthenticationError as exc: raise agent_authentication_required() from exc


def authorization_action_for_agent(identity: AuthenticatedAgent, **action_fields: object) -> AuthorizationAction:
    """Build future Approval Manager input from trusted identity, never caller actor IDs."""
    forbidden = {"company_id", "actor_type", "actor_administrator_id", "actor_agent_id"}
    if forbidden.intersection(action_fields): raise ValueError("Actor identity fields are controlled by authentication.")
    return AuthorizationAction(company_id=identity.agent.company_id, actor_type="agent", actor_agent_id=identity.agent.id, **action_fields)
