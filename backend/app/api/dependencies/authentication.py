"""FastAPI dependency for authenticated administrators."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.core.security import InvalidAccessTokenError
from app.models.administrator import Administrator
from app.services.authentication import (
    AdministratorInactiveError,
    AuthenticationService,
    get_authentication_service,
)

_bearer_scheme = HTTPBearer(
    auto_error=False,
)


def authentication_required_exception() -> HTTPException:
    """Create the standard authentication-required response."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid administrator authentication is required.",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


def require_current_administrator(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
    service: Annotated[
        AuthenticationService,
        Depends(get_authentication_service),
    ],
) -> Administrator:
    """Return the active administrator represented by a Bearer token."""

    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not credentials.credentials
    ):
        raise authentication_required_exception()

    try:
        return service.resolve_access_token(
            credentials.credentials
        )
    except (
        InvalidAccessTokenError,
        AdministratorInactiveError,
    ) as exc:
        raise authentication_required_exception() from exc
