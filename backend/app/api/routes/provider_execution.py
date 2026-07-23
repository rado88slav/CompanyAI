from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.api.dependencies.agent_authentication import require_current_agent
from app.api.dependencies.authentication import require_current_administrator
from app.api.dependencies.company_authorization import require_provider_executions_manage, require_provider_executions_read
from app.core.provider_execution import provider_operation_registry
from app.models.administrator import Administrator
from app.schemas.company_context import ActiveCompanyContext
from app.schemas.provider_execution import ProviderExecutionAuthorize, ProviderExecutionCreate, ProviderExecutionListResponse, ProviderExecutionResponse, ProviderOperationResponse
from app.services.agent_identity import AuthenticatedAgent
from app.services.provider_execution import ExecutionConflictError, ExecutionDeniedError, ExecutionNotFoundError, ExecutionValidationError, ProviderExecutionService, get_provider_execution_service

router=APIRouter(tags=["provider-execution"])
def err(exc):
    if isinstance(exc, ExecutionNotFoundError): raise HTTPException(404,"Provider execution was not found.") from exc
    if isinstance(exc, ExecutionDeniedError): raise HTTPException(403,"Provider execution is denied.") from exc
    if isinstance(exc,(ExecutionConflictError,ExecutionValidationError)): raise HTTPException(409,"Provider execution conflicts with current state.") from exc
    raise exc

@router.get("/provider-operations", response_model=list[ProviderOperationResponse])
def list_operations(_a: Annotated[Administrator,Depends(require_current_administrator)]): return [ProviderOperationResponse.from_descriptor(x) for x in provider_operation_registry.all()]
@router.get("/provider-operations/{provider_key}/{operation_key}", response_model=ProviderOperationResponse)
def get_operation(provider_key: str, operation_key: str, _a: Annotated[Administrator,Depends(require_current_administrator)]):
    item=provider_operation_registry.get(provider_key,operation_key)
    if item is None: raise HTTPException(404,"Provider operation was not found.")
    return ProviderOperationResponse.from_descriptor(item)

@router.post("/companies/{company_id}/provider-executions", response_model=ProviderExecutionResponse, status_code=status.HTTP_201_CREATED)
def create_execution(company_id: UUID, data: ProviderExecutionCreate, context: Annotated[ActiveCompanyContext,Depends(require_provider_executions_manage)], service: Annotated[ProviderExecutionService,Depends(get_provider_execution_service)]):
    try: return service.create(company_id=company_id,data=data,administrator=context.administrator)
    except Exception as exc: err(exc)
@router.get("/companies/{company_id}/provider-executions", response_model=ProviderExecutionListResponse)
def list_executions(company_id: UUID, _c: Annotated[ActiveCompanyContext,Depends(require_provider_executions_read)], service: Annotated[ProviderExecutionService,Depends(get_provider_execution_service)], limit: int=Query(50,ge=1,le=100), offset: int=Query(0,ge=0)):
    items,total=service.list(company_id,limit,offset); return ProviderExecutionListResponse(items=items,total=total,limit=limit,offset=offset)
@router.get("/companies/{company_id}/provider-executions/{execution_id}", response_model=ProviderExecutionResponse)
def get_execution(company_id: UUID, execution_id: UUID, _c: Annotated[ActiveCompanyContext,Depends(require_provider_executions_read)], service: Annotated[ProviderExecutionService,Depends(get_provider_execution_service)]):
    try: return service.get(company_id,execution_id)
    except Exception as exc: err(exc)
@router.post("/companies/{company_id}/provider-executions/{execution_id}/execute-dry-run", response_model=ProviderExecutionResponse)
def execute_dry_run(company_id: UUID, execution_id: UUID, data: ProviderExecutionAuthorize, context: Annotated[ActiveCompanyContext,Depends(require_provider_executions_manage)], service: Annotated[ProviderExecutionService,Depends(get_provider_execution_service)]):
    try: return service.execute_dry_run(company_id=company_id,execution_id=execution_id,administrator=context.administrator,authorization_policy_id=data.authorization_policy_id)
    except Exception as exc: err(exc)
@router.post("/companies/{company_id}/provider-executions/{execution_id}/cancel", response_model=ProviderExecutionResponse)
def cancel_execution(company_id: UUID, execution_id: UUID, context: Annotated[ActiveCompanyContext,Depends(require_provider_executions_manage)], service: Annotated[ProviderExecutionService,Depends(get_provider_execution_service)]):
    try: return service.cancel(company_id=company_id, execution_id=execution_id, administrator=context.administrator)
    except Exception as exc: err(exc)

@router.get("/internal/agents/provider-operations", response_model=list[ProviderOperationResponse])
def agent_operations(identity: Annotated[AuthenticatedAgent,Depends(require_current_agent)], service: Annotated[ProviderExecutionService,Depends(get_provider_execution_service)]): return [ProviderOperationResponse.from_descriptor(x) for x in service.available_operations(company_id=identity.agent.company_id, agent_id=identity.agent.id)]
@router.post("/internal/agents/provider-executions", response_model=ProviderExecutionResponse, status_code=201)
def agent_create(data: ProviderExecutionCreate, identity: Annotated[AuthenticatedAgent,Depends(require_current_agent)], service: Annotated[ProviderExecutionService,Depends(get_provider_execution_service)]):
    try: return service.create(company_id=identity.agent.company_id,data=data,agent_id=identity.agent.id)
    except Exception as exc: err(exc)
@router.post("/internal/agents/provider-executions/{execution_id}/execute-dry-run", response_model=ProviderExecutionResponse)
def agent_execute(execution_id: UUID, data: ProviderExecutionAuthorize, identity: Annotated[AuthenticatedAgent,Depends(require_current_agent)], service: Annotated[ProviderExecutionService,Depends(get_provider_execution_service)]):
    try: return service.execute_dry_run(company_id=identity.agent.company_id,execution_id=execution_id,agent_id=identity.agent.id,authorization_policy_id=data.authorization_policy_id)
    except Exception as exc: err(exc)
