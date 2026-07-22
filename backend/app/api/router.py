"""Main API router."""

from fastapi import APIRouter

from app.api.routes.authentication import (
    router as authentication_router,
)
from app.api.routes.companies import router as companies_router
from app.api.routes.company_context import router as company_context_router
from app.api.routes.company_settings import (
    router as company_settings_router,
)
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(authentication_router)
api_router.include_router(companies_router)
api_router.include_router(company_context_router)
api_router.include_router(company_settings_router)
