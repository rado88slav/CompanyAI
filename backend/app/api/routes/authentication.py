"""HTTP endpoints for administrator authentication."""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from app.api.dependencies.authentication import (
    require_current_administrator,
)
from app.models.administrator import Administrator
from app.schemas.authentication import (
    AdministratorResponse,
    LoginRequest,
    TokenResponse,
)
from app.services.authentication import (
    AdministratorInactiveError,
    AuthenticationService,
    InvalidCredentialsError,
    get_authentication_service,
)

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)


def invalid_login_exception() -> HTTPException:
    """Create a generic login failure without revealing account state."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate an administrator",
)
def login_administrator(
    login_data: LoginRequest,
    service: Annotated[
        AuthenticationService,
        Depends(get_authentication_service),
    ],
) -> TokenResponse:
    """Validate credentials and issue a signed access token."""

    try:
        administrator = service.authenticate(login_data)
    except (
        InvalidCredentialsError,
        AdministratorInactiveError,
    ) as exc:
        raise invalid_login_exception() from exc

    issued_token = service.issue_access_token(
        administrator
    )

    return TokenResponse(
        access_token=issued_token.access_token,
        expires_in=issued_token.expires_in,
    )


@router.get(
    "/me",
    response_model=AdministratorResponse,
    summary="Get the current administrator",
)
def get_current_administrator(
    administrator: Annotated[
        Administrator,
        Depends(require_current_administrator),
    ],
) -> AdministratorResponse:
    """Return the authenticated administrator account."""

    return AdministratorResponse.model_validate(
        administrator
    )
