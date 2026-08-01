"""Trusted provider operation registry and fail-closed adapter contracts."""
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping, Protocol

class ExecutionMode(StrEnum):
    DRY_RUN = "dry_run"
    LIVE = "live"

class ExecutionRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass(frozen=True, slots=True)
class ProviderOperationDescriptor:
    provider_key: str
    operation_key: str
    display_name: str
    description: str
    category: str
    risk_level: ExecutionRisk
    approval_required: bool
    supported_execution_modes: frozenset[ExecutionMode]
    required_connection_status: str = "active"
    required_credential_status: str = "active"
    input_fields: frozenset[str] = frozenset()
    redaction_fields: frozenset[str] = frozenset()
    idempotency_supported: bool = True
    timeout_seconds: int = 30
    retry_attempts: int = 0
    implemented: bool = False

class ProviderOperationRegistry:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], ProviderOperationDescriptor] = {}
    def register(self, descriptor: ProviderOperationDescriptor) -> None:
        key = (descriptor.provider_key, descriptor.operation_key)
        if key in self._items: raise ValueError("Provider operation is already registered.")
        self._items[key] = descriptor
    def get(self, provider_key: str, operation_key: str) -> ProviderOperationDescriptor | None:
        return self._items.get((provider_key, operation_key))
    def require(self, provider_key: str, operation_key: str) -> ProviderOperationDescriptor:
        item = self.get(provider_key, operation_key)
        if item is None: raise ValueError("Provider operation was not found.")
        return item
    def all(self) -> tuple[ProviderOperationDescriptor, ...]:
        return tuple(self._items[key] for key in sorted(self._items))
    @property
    def descriptors(self) -> Mapping[tuple[str, str], ProviderOperationDescriptor]:
        return MappingProxyType(self._items)

class ProviderAdapter(Protocol):
    name: str
    def execute(self, descriptor: ProviderOperationDescriptor, payload: Mapping[str, Any], *, idempotency_key: str) -> dict[str, Any]: ...

class DryRunProviderAdapter:
    name = "dry-run"
    def execute(self, descriptor: ProviderOperationDescriptor, payload: Mapping[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        return {"simulated": True, "provider_key": descriptor.provider_key, "operation_key": descriptor.operation_key, "idempotency_key": idempotency_key}

class UnsupportedProviderAdapter:
    name = "unsupported-live"
    def execute(self, descriptor: ProviderOperationDescriptor, payload: Mapping[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        raise RuntimeError("Live provider execution is not implemented.")

class LocalTestEmailAdapter:
    """Development-only deterministic email delivery without network access."""
    name = "local-test-email"
    def execute(self, descriptor: ProviderOperationDescriptor, payload: Mapping[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        if payload.get("controlled_failure") is True:
            raise RuntimeError("Controlled local test delivery failure.")
        import hashlib
        return {
            "provider_message_id": "local-test-" + hashlib.sha256(idempotency_key.encode()).hexdigest()[:24],
            "delivery": "test",
        }

provider_operation_registry = ProviderOperationRegistry()
provider_operation_registry.register(ProviderOperationDescriptor(
    "local_test_email", "send_email", "Test delivery",
    "Development-only deterministic email delivery.", "email",
    ExecutionRisk.HIGH, True, frozenset({ExecutionMode.DRY_RUN}),
    required_credential_status="not_required",
    input_fields=frozenset({"recipient_email", "subject", "body", "controlled_failure"}),
    redaction_fields=frozenset({"body"}), implemented=True,
))
provider_operation_registry.register(ProviderOperationDescriptor(
    "generic_smtp_imap", "send_email", "Generic SMTP/IMAP email send",
    "Approval-gated single-message email boundary. Live adapter is not implemented.", "email",
    ExecutionRisk.HIGH, True, frozenset({ExecutionMode.DRY_RUN, ExecutionMode.LIVE}),
    input_fields=frozenset({"sender_email", "recipient_email", "subject", "body", "payload_digest", "confirmation_text"}),
    redaction_fields=frozenset({"body"}), timeout_seconds=15, retry_attempts=0, implemented=False,
))
for _provider, _ops in {
    "retell": ("list_agents", "get_agent", "create_call"), "twilio": ("list_phone_numbers", "get_call", "create_call"),
    "telnyx": ("list_phone_numbers", "get_call", "create_call"), "microsoft_365": ("list_mailboxes", "send_email"),
    "google_workspace": ("list_mailboxes", "send_email"), "lemlist": ("list_campaigns", "get_campaign", "add_lead"),
    "instantly": ("list_campaigns", "get_campaign", "add_lead"), "smartlead": ("list_campaigns", "get_campaign", "add_lead"),
}.items():
    for _op in _ops:
        _mutating = _op in {"create_call", "send_email", "add_lead"}
        provider_operation_registry.register(ProviderOperationDescriptor(_provider, _op, _op.replace("_", " ").title(), "Trusted provider operation.", "provider", ExecutionRisk.HIGH if _mutating else ExecutionRisk.LOW, _mutating, frozenset({ExecutionMode.DRY_RUN, ExecutionMode.LIVE}), input_fields=frozenset(), redaction_fields=frozenset({"token", "secret", "password", "api_key"}), implemented=False))
