from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.core.provider_execution import ExecutionMode, ExecutionRisk, ProviderOperationDescriptor

class ProviderOperationResponse(BaseModel):
    provider_key: str; operation_key: str; display_name: str; description: str; category: str; risk_level: ExecutionRisk; approval_required: bool; supported_execution_modes: list[ExecutionMode]; required_connection_status: str; required_credential_status: str; input_fields: list[str]; redaction_fields: list[str]; idempotency_supported: bool; timeout_seconds: int; retry_attempts: int; implemented: bool
    @classmethod
    def from_descriptor(cls, d: ProviderOperationDescriptor): return cls(provider_key=d.provider_key, operation_key=d.operation_key, display_name=d.display_name, description=d.description, category=d.category, risk_level=d.risk_level, approval_required=d.approval_required, supported_execution_modes=sorted(d.supported_execution_modes, key=lambda x:x.value), required_connection_status=d.required_connection_status, required_credential_status=d.required_credential_status, input_fields=sorted(d.input_fields), redaction_fields=sorted(d.redaction_fields), idempotency_supported=d.idempotency_supported, timeout_seconds=d.timeout_seconds, retry_attempts=d.retry_attempts, implemented=d.implemented)

class ProviderExecutionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_connection_id: UUID; provider_key: str; operation_key: str; execution_mode: ExecutionMode = ExecutionMode.DRY_RUN; idempotency_key: str = Field(min_length=1, max_length=200); request_payload: dict = Field(default_factory=dict)

class ProviderExecutionAuthorize(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authorization_policy_id: UUID | None = None

class ProviderExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; company_id: UUID; provider_connection_id: UUID; provider_key: str; operation_key: str; execution_mode: ExecutionMode; status: str; requested_by_administrator_id: UUID | None; requested_by_agent_id: UUID | None; authorization_reference: UUID | None; idempotency_key: str; request_payload: dict; result_metadata: dict; error_category: str | None; error_message: str | None; created_at: datetime; started_at: datetime | None; completed_at: datetime | None; cancelled_at: datetime | None; updated_at: datetime

class ProviderExecutionListResponse(BaseModel):
    items: list[ProviderExecutionResponse]; total: int; limit: int; offset: int
