"""Trusted provider catalog and company-scoped connection metadata APIs."""

from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.authentication import require_current_administrator
from app.api.dependencies.company_authorization import require_providers_manage, require_providers_read
from app.core.config import Settings, get_settings
from app.core.provider_connections import provider_registry
from app.models.administrator import Administrator
from app.schemas.company_context import ActiveCompanyContext
from app.schemas.provider_connection import ProviderConnectionCreate, ProviderConnectionListResponse, ProviderConnectionResponse, ProviderConnectionTestResponse, ProviderConnectionUpdate, ProviderCredentialCreate, ProviderCredentialListResponse, ProviderCredentialResponse, ProviderDescriptorResponse
from app.services.generic_smtp_imap import MailboxProtocol
from app.services.provider_connection import ProviderConflictError, ProviderConnectionService, ProviderLifecycleError, ProviderNotFoundError, get_provider_connection_service

router = APIRouter(tags=["provider-connections"])


def _connection_response(item, service: ProviderConnectionService) -> ProviderConnectionResponse:
    response = ProviderConnectionResponse.model_validate(item)
    return response.model_copy(update={"credential_status": service.credential_status(item)})


def _error(exc: Exception) -> None:
    if isinstance(exc, ProviderNotFoundError):
        raise HTTPException(404, "Provider connection resource was not found.") from exc
    if isinstance(exc, (ProviderConflictError, ProviderLifecycleError, ValueError)):
        raise HTTPException(409, "Provider connection operation conflicts with current state.") from exc
    raise exc


@router.get("/provider-types", response_model=list[ProviderDescriptorResponse])
def list_provider_types(_actor: Annotated[Administrator, Depends(require_current_administrator)]) -> list[ProviderDescriptorResponse]:
    return [ProviderDescriptorResponse.from_descriptor(item) for item in provider_registry.all()]


@router.get("/provider-types/{provider_key}", response_model=ProviderDescriptorResponse)
def get_provider_type(provider_key: str, _actor: Annotated[Administrator, Depends(require_current_administrator)]) -> ProviderDescriptorResponse:
    item = provider_registry.get(provider_key)
    if item is None: raise HTTPException(404, "Provider type was not found.")
    return ProviderDescriptorResponse.from_descriptor(item)


@router.post("/companies/{company_id}/provider-connections", response_model=ProviderConnectionResponse, status_code=201)
def create_connection(company_id: UUID, data: ProviderConnectionCreate, context: Annotated[ActiveCompanyContext, Depends(require_providers_manage)], service: Annotated[ProviderConnectionService, Depends(get_provider_connection_service)]) -> ProviderConnectionResponse:
    try: return _connection_response(service.create_connection(company_id=company_id, data=data, actor=context.administrator), service)
    except (ProviderConflictError, ProviderLifecycleError, ProviderNotFoundError, ValueError) as exc: _error(exc)


@router.post("/companies/{company_id}/provider-connections/local-test-email/setup", response_model=ProviderConnectionResponse)
def setup_local_test_email_connection(
    company_id: UUID,
    context: Annotated[ActiveCompanyContext, Depends(require_providers_manage)],
    service: Annotated[ProviderConnectionService, Depends(get_provider_connection_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProviderConnectionResponse:
    try:
        return _connection_response(
            service.setup_local_test_email_connection(
                company_id=company_id,
                actor=context.administrator,
                app_environment=settings.app_environment,
            ),
            service,
        )
    except (ProviderConflictError, ProviderLifecycleError, ProviderNotFoundError, ValueError) as exc:
        _error(exc)


@router.get("/companies/{company_id}/provider-connections", response_model=ProviderConnectionListResponse)
def list_connections(company_id: UUID, _context: Annotated[ActiveCompanyContext, Depends(require_providers_read)], service: Annotated[ProviderConnectionService, Depends(get_provider_connection_service)], limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)) -> ProviderConnectionListResponse:
    items, total = service.list_connections(company_id=company_id, limit=limit, offset=offset)
    return ProviderConnectionListResponse(items=[_connection_response(item, service) for item in items], total=total, limit=limit, offset=offset)


@router.get("/companies/{company_id}/provider-connections/{connection_id}", response_model=ProviderConnectionResponse)
def get_connection(company_id: UUID, connection_id: UUID, _context: Annotated[ActiveCompanyContext, Depends(require_providers_read)], service: Annotated[ProviderConnectionService, Depends(get_provider_connection_service)]) -> ProviderConnectionResponse:
    try: return _connection_response(service.get_connection(company_id=company_id, connection_id=connection_id), service)
    except ProviderNotFoundError as exc: _error(exc)


@router.patch("/companies/{company_id}/provider-connections/{connection_id}", response_model=ProviderConnectionResponse)
def update_connection(company_id: UUID, connection_id: UUID, data: ProviderConnectionUpdate, context: Annotated[ActiveCompanyContext, Depends(require_providers_manage)], service: Annotated[ProviderConnectionService, Depends(get_provider_connection_service)]) -> ProviderConnectionResponse:
    try: return _connection_response(service.update_connection(company_id=company_id, connection_id=connection_id, data=data, actor=context.administrator), service)
    except (ProviderConflictError, ProviderLifecycleError, ProviderNotFoundError, ValueError) as exc: _error(exc)


def _status(company_id: UUID, connection_id: UUID, target: str, context: ActiveCompanyContext, service: ProviderConnectionService) -> ProviderConnectionResponse:
    try: return _connection_response(service.set_status(company_id=company_id, connection_id=connection_id, target=target, actor=context.administrator), service)
    except (ProviderLifecycleError, ProviderNotFoundError) as exc: _error(exc)


@router.post("/companies/{company_id}/provider-connections/{connection_id}/activate", response_model=ProviderConnectionResponse)
def activate(company_id: UUID, connection_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_providers_manage)], service: Annotated[ProviderConnectionService, Depends(get_provider_connection_service)]) -> ProviderConnectionResponse: return _status(company_id, connection_id, "active", context, service)
@router.post("/companies/{company_id}/provider-connections/{connection_id}/deactivate", response_model=ProviderConnectionResponse)
def deactivate(company_id: UUID, connection_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_providers_manage)], service: Annotated[ProviderConnectionService, Depends(get_provider_connection_service)]) -> ProviderConnectionResponse: return _status(company_id, connection_id, "inactive", context, service)
@router.post("/companies/{company_id}/provider-connections/{connection_id}/revoke", response_model=ProviderConnectionResponse)
def revoke(company_id: UUID, connection_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_providers_manage)], service: Annotated[ProviderConnectionService, Depends(get_provider_connection_service)]) -> ProviderConnectionResponse: return _status(company_id, connection_id, "revoked", context, service)


def _mailbox_test(company_id: UUID, connection_id: UUID, protocol: MailboxProtocol, context: ActiveCompanyContext, service: ProviderConnectionService) -> ProviderConnectionTestResponse:
    try:
        result, connection = service.test_generic_mailbox(company_id=company_id, connection_id=connection_id, protocol=protocol, actor=context.administrator)
        return ProviderConnectionTestResponse(protocol=result.protocol.value, status=result.status, tested_at=result.tested_at, category=result.category.value, message=result.message, connection=_connection_response(connection, service))
    except (ProviderLifecycleError, ProviderNotFoundError) as exc:
        _error(exc)


@router.post("/companies/{company_id}/provider-connections/{connection_id}/test-smtp", response_model=ProviderConnectionTestResponse)
def test_smtp(company_id: UUID, connection_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_providers_manage)], service: Annotated[ProviderConnectionService, Depends(get_provider_connection_service)]) -> ProviderConnectionTestResponse:
    return _mailbox_test(company_id, connection_id, MailboxProtocol.SMTP, context, service)


@router.post("/companies/{company_id}/provider-connections/{connection_id}/test-imap", response_model=ProviderConnectionTestResponse)
def test_imap(company_id: UUID, connection_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_providers_manage)], service: Annotated[ProviderConnectionService, Depends(get_provider_connection_service)]) -> ProviderConnectionTestResponse:
    return _mailbox_test(company_id, connection_id, MailboxProtocol.IMAP, context, service)


@router.get("/companies/{company_id}/provider-connections/{connection_id}/credentials", response_model=ProviderCredentialListResponse)
def list_credentials(company_id: UUID, connection_id: UUID, _context: Annotated[ActiveCompanyContext, Depends(require_providers_read)], service: Annotated[ProviderConnectionService, Depends(get_provider_connection_service)], limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)) -> ProviderCredentialListResponse:
    try:
        items, total = service.list_credentials(company_id=company_id, connection_id=connection_id, limit=limit, offset=offset)
        return ProviderCredentialListResponse(items=[ProviderCredentialResponse.model_validate(item) for item in items], total=total, limit=limit, offset=offset)
    except ProviderNotFoundError as exc: _error(exc)


@router.post("/companies/{company_id}/provider-connections/{connection_id}/credentials", response_model=ProviderCredentialResponse, status_code=201)
def create_credential(company_id: UUID, connection_id: UUID, data: ProviderCredentialCreate, context: Annotated[ActiveCompanyContext, Depends(require_providers_manage)], service: Annotated[ProviderConnectionService, Depends(get_provider_connection_service)]) -> ProviderCredentialResponse:
    try: return ProviderCredentialResponse.model_validate(service.create_credential(company_id=company_id, connection_id=connection_id, data=data, actor=context.administrator))
    except (ProviderConflictError, ProviderLifecycleError, ProviderNotFoundError, ValueError) as exc: _error(exc)


@router.post("/companies/{company_id}/provider-connections/{connection_id}/credentials/{credential_id}/rotate", response_model=ProviderCredentialResponse, status_code=201)
def rotate_credential(company_id: UUID, connection_id: UUID, credential_id: UUID, data: ProviderCredentialCreate, context: Annotated[ActiveCompanyContext, Depends(require_providers_manage)], service: Annotated[ProviderConnectionService, Depends(get_provider_connection_service)]) -> ProviderCredentialResponse:
    try: return ProviderCredentialResponse.model_validate(service.rotate_credential(company_id=company_id, connection_id=connection_id, credential_id=credential_id, data=data, actor=context.administrator))
    except (ProviderConflictError, ProviderLifecycleError, ProviderNotFoundError, ValueError) as exc: _error(exc)


@router.post("/companies/{company_id}/provider-connections/{connection_id}/credentials/{credential_id}/revoke", response_model=ProviderCredentialResponse)
def revoke_credential(company_id: UUID, connection_id: UUID, credential_id: UUID, context: Annotated[ActiveCompanyContext, Depends(require_providers_manage)], service: Annotated[ProviderConnectionService, Depends(get_provider_connection_service)]) -> ProviderCredentialResponse:
    try: return ProviderCredentialResponse.model_validate(service.revoke_credential(company_id=company_id, connection_id=connection_id, credential_id=credential_id, actor=context.administrator))
    except (ProviderConflictError, ProviderLifecycleError, ProviderNotFoundError) as exc: _error(exc)
