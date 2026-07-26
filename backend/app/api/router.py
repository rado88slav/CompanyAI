"""Main API router."""

from fastapi import APIRouter

from app.api.routes.authentication import (
    router as authentication_router,
)
from app.api.routes.agent_authentication import router as agent_authentication_router
from app.api.routes.agent_runtime import router as agent_runtime_router
from app.api.routes.agents import router as agents_router
from app.api.routes.approvals import router as approvals_router
from app.api.routes.companies import router as companies_router
from app.api.routes.company_activity import router as company_activity_router
from app.api.routes.company_context import router as company_context_router
from app.api.routes.company_memberships import router as company_memberships_router
from app.api.routes.company_settings import (
    router as company_settings_router,
)
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.health import router as health_router
from app.api.routes.tool_registry import router as tool_registry_router
from app.api.routes.provider_connections import router as provider_connections_router
from app.api.routes.provider_execution import router as provider_execution_router
from app.api.routes.email import router as email_router
from app.api.routes.email_campaigns import router as email_campaigns_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(authentication_router)
api_router.include_router(agent_authentication_router)
api_router.include_router(agent_runtime_router)
api_router.include_router(agents_router)
api_router.include_router(approvals_router)
api_router.include_router(companies_router)
api_router.include_router(company_activity_router)
api_router.include_router(company_context_router)
api_router.include_router(company_memberships_router)
api_router.include_router(company_settings_router)
api_router.include_router(dashboard_router)
api_router.include_router(tool_registry_router)
api_router.include_router(provider_connections_router)
api_router.include_router(provider_execution_router)
api_router.include_router(email_router)
api_router.include_router(email_campaigns_router)
