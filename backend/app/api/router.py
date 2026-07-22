"""Main API router."""

from fastapi import APIRouter

from app.api.routes.companies import router as companies_router
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(companies_router)
