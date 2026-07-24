"""Company AI FastAPI application entry point."""

from fastapi import FastAPI
from pydantic import BaseModel

from app.api.router import api_router
from app.core.config import get_settings
from app.core.credential_encryption import decode_encryption_key


class RootResponse(BaseModel):
    """Root endpoint response."""

    service: str
    environment: str
    version: str
    documentation: str


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    decode_encryption_key(settings.credential_encryption_key)

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    application.include_router(
        api_router,
        prefix=settings.api_prefix,
    )

    @application.get(
        "/",
        response_model=RootResponse,
        tags=["system"],
        summary="Show backend information",
    )
    def read_root() -> RootResponse:
        return RootResponse(
            service=settings.app_name,
            environment=settings.app_environment,
            version=settings.app_version,
            documentation="/docs",
        )

    return application


app = create_application()
