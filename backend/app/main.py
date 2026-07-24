"""Company AI FastAPI application entry point."""

from fastapi import FastAPI
from pydantic import BaseModel

from app.api.router import api_router
from app.core.config import get_settings
from app.core.credential_encryption import parse_runtime_encryption_keyring


class RootResponse(BaseModel):
    """Root endpoint response."""

    service: str
    environment: str
    version: str
    documentation: str


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    keyring = parse_runtime_encryption_keyring(
        settings.credential_encryption_keyring,
        active_key_id=settings.credential_encryption_active_key_id,
        legacy_key_configured=(
            settings.credential_encryption_legacy_key_present
        ),
    )

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    application.state.credential_encryption_keyring = keyring

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
