#!/usr/bin/env bash
# Description: Add stateless superuser-selected Active Company Context and Company Settings isolation.

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"

printf '%s\n' "======================================"
printf '%s\n' " Company AI - Add Active Context"
printf '%s\n' "======================================"
printf '\n'

mkdir -p \
    "${BACKEND_DIR}/app/api/dependencies" \
    "${BACKEND_DIR}/app/api/routes" \
    "${BACKEND_DIR}/app/schemas"

cat > "${BACKEND_DIR}/app/schemas/company_context.py" <<'PYTHON'
"""Typed request and response schemas for active company context."""

from dataclasses import dataclass

from pydantic import BaseModel

from app.models.administrator import Administrator
from app.models.company import Company
from app.schemas.company import CompanyResponse


@dataclass(frozen=True, slots=True)
class ActiveCompanyContext:
    """Authenticated administrator and company resolved for one request."""

    administrator: Administrator
    company: Company


class ActiveCompanyContextResponse(BaseModel):
    """Public representation of the resolved active company context."""

    company: CompanyResponse
PYTHON

cat > "${BACKEND_DIR}/app/api/dependencies/company_context.py" <<'PYTHON'
"""FastAPI dependencies for stateless active company context."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Path, status

from app.api.dependencies.authentication import require_current_administrator
from app.models.administrator import Administrator
from app.models.company import CompanyStatus
from app.schemas.company_context import ActiveCompanyContext
from app.services.company import (
    CompanyNotFoundError,
    CompanyService,
    get_company_service,
)


def invalid_company_header_exception() -> HTTPException:
    """Create the standard invalid company-header response."""

    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="X-Company-ID header must contain a valid company UUID.",
    )


def require_active_company_context(
    administrator: Annotated[
        Administrator,
        Depends(require_current_administrator),
    ],
    service: Annotated[
        CompanyService,
        Depends(get_company_service),
    ],
    company_header: Annotated[
        str | None,
        Header(alias="X-Company-ID"),
    ] = None,
) -> ActiveCompanyContext:
    """Resolve an active company selected by an authenticated superuser."""

    if company_header is None or not company_header.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Company-ID header is required.",
        )

    try:
        company_id = UUID(company_header.strip())
    except (ValueError, AttributeError) as exc:
        raise invalid_company_header_exception() from exc

    if not administrator.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access is required to select a company context.",
        )

    try:
        company = service.get_company(company_id)
    except CompanyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company was not found.",
        ) from exc

    if not company.is_active or company.status != CompanyStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inactive company cannot be selected as active context.",
        )

    return ActiveCompanyContext(
        administrator=administrator,
        company=company,
    )


def require_matching_active_company(
    company_id: Annotated[UUID, Path()],
    context: Annotated[
        ActiveCompanyContext,
        Depends(require_active_company_context),
    ],
) -> ActiveCompanyContext:
    """Require a company path UUID to match the selected request context."""

    if company_id != context.company.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="URL company_id must match the X-Company-ID company context.",
        )

    return context
PYTHON

cat > "${BACKEND_DIR}/app/api/routes/company_context.py" <<'PYTHON'
"""HTTP endpoint for resolving active company context."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies.company_context import require_active_company_context
from app.schemas.company import CompanyResponse
from app.schemas.company_context import (
    ActiveCompanyContext,
    ActiveCompanyContextResponse,
)

router = APIRouter(tags=["company-context"])


@router.get(
    "/company-context",
    response_model=ActiveCompanyContextResponse,
    summary="Resolve the active company context",
)
def get_active_company_context(
    context: Annotated[
        ActiveCompanyContext,
        Depends(require_active_company_context),
    ],
) -> ActiveCompanyContextResponse:
    """Return the company selected for the current request."""

    return ActiveCompanyContextResponse(
        company=CompanyResponse.model_validate(context.company),
    )
PYTHON

cat > "${BACKEND_DIR}/app/api/dependencies/__init__.py" <<'PYTHON'
"""Reusable FastAPI dependencies."""

from app.api.dependencies.company_context import (
    require_active_company_context,
    require_matching_active_company,
)

__all__ = [
    "require_active_company_context",
    "require_matching_active_company",
]
PYTHON

if ! grep -q 'company_context_router' "${BACKEND_DIR}/app/api/router.py"; then
    sed -i \
        '/from app.api.routes.companies import router as companies_router/a from app.api.routes.company_context import router as company_context_router' \
        "${BACKEND_DIR}/app/api/router.py"
    sed -i \
        '/api_router.include_router(companies_router)/a api_router.include_router(company_context_router)' \
        "${BACKEND_DIR}/app/api/router.py"
fi

if ! grep -q 'ActiveCompanyContextResponse' "${BACKEND_DIR}/app/schemas/__init__.py"; then
    sed -i \
        '/from app.schemas.company_setting import (/i from app.schemas.company_context import (\
    ActiveCompanyContext,\
    ActiveCompanyContextResponse,\
)' \
        "${BACKEND_DIR}/app/schemas/__init__.py"
    sed -i \
        '/__all__ = \[/a\    "ActiveCompanyContext",\
    "ActiveCompanyContextResponse",' \
        "${BACKEND_DIR}/app/schemas/__init__.py"
fi

SETTINGS_ROUTE="${BACKEND_DIR}/app/api/routes/company_settings.py"

if ! grep -q 'require_matching_active_company' "${SETTINGS_ROUTE}"; then
    sed -i \
        '/from app.api.dependencies.authentication import (/i from app.api.dependencies.company_context import (\
    require_matching_active_company,\
)' \
        "${SETTINGS_ROUTE}"
    sed -i \
        '/from app.schemas.company_setting import (/i from app.schemas.company_context import ActiveCompanyContext' \
        "${SETTINGS_ROUTE}"

    for function_name in \
        upsert_company_setting \
        list_company_settings \
        get_company_setting \
        delete_company_setting
    do
        sed -i \
            "/^def ${function_name}(/,/^    company_id: UUID,$/ {\
                /^    company_id: UUID,$/a\\
    _context: Annotated[\\
        ActiveCompanyContext,\\
        Depends(require_matching_active_company),\\
    ],
            }" \
            "${SETTINGS_ROUTE}"
    done
fi

SETTINGS_TEST="${BACKEND_DIR}/tests/test_company_settings.py"

if ! grep -q 'require_matching_active_company' "${SETTINGS_TEST}"; then
    sed -i \
        '/from app.main import app/i from app.api.dependencies.company_context import (\
    require_matching_active_company,\
)\
' \
        "${SETTINGS_TEST}"
    sed -i \
        '/^    app.dependency_overrides\[$/,/^    \] = lambda: object()$/ {\
            /^    \] = lambda: object()$/a\\
\
    app.dependency_overrides[\\
        require_matching_active_company\\
    ] = lambda: object()
        }' \
        "${SETTINGS_TEST}"
fi

printf '%s\n' "Active Company Context foundation is present."
printf '%s\n' "No database migration was created or applied."

if [[ -x "${PROJECT_ROOT}/scripts/maintenance/update-project-status.sh" ]]; then
    "${PROJECT_ROOT}/scripts/maintenance/update-project-status.sh"
fi

printf '\n%s\n' "Active Company Context setup completed successfully."
