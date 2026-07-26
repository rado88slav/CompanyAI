"""Safe tool-key validation and trusted in-process runtime descriptors."""

from dataclasses import dataclass
import re
from typing import Callable


TOOL_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_FORBIDDEN_SCHEMA_KEY_PARTS = frozenset(
    {
        "password", "secret", "token", "api_key", "access_key", "private_key",
        "credential", "handler", "command", "shell", "import", "module",
        "source_code", "callable", "entrypoint", "executable",
    }
)


def validate_tool_key(value: str) -> str:
    """Return an exact canonical tool key or reject it without changing meaning."""

    if not isinstance(value, str) or not TOOL_KEY_PATTERN.fullmatch(value):
        raise ValueError("Tool key must be lowercase, dot-separated and contain no wildcards.")
    return value


def validate_safe_tool_object(value: object, *, path: str) -> dict[str, object]:
    """Reject non-object and recursively secret-bearing or executable metadata."""

    if not isinstance(value, dict):
        raise ValueError(f"{path} must be a JSON object.")

    def visit(item: object, current_path: str) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                if not isinstance(key, str):
                    raise ValueError(f"{current_path} keys must be strings.")
                normalized = key.strip().lower().replace("-", "_")
                if any(part in normalized for part in _FORBIDDEN_SCHEMA_KEY_PARTS):
                    raise ValueError(f"Unsafe tool field: {current_path}.{key}")
                visit(nested, f"{current_path}.{key}")
            return
        if isinstance(item, list):
            for index, nested in enumerate(item):
                visit(nested, f"{current_path}[{index}]")
            return
        if item is None or isinstance(item, (str, int, float, bool)):
            return
        raise ValueError(f"{current_path} contains a non-JSON value.")

    visit(value, path)
    return value


@dataclass(frozen=True, slots=True)
class RuntimeToolDescriptor:
    """Trusted application-code registration, never persisted in the database."""

    key: str
    implementation_name: str
    execution_mode: str
    callable_ref: Callable[..., object] | None = None

    def __post_init__(self) -> None:
        validate_tool_key(self.key)
        if self.execution_mode not in {"internal", "provider", "external_executor"}:
            raise ValueError("Unsupported descriptor execution mode.")
        if not self.implementation_name.strip():
            raise ValueError("implementation_name is required.")


class RuntimeToolRegistry:
    """Exact-key registry populated only through trusted Python code."""

    def __init__(self) -> None:
        self._descriptors: dict[str, RuntimeToolDescriptor] = {}

    def register(self, descriptor: RuntimeToolDescriptor) -> None:
        if descriptor.key in self._descriptors:
            raise ValueError("Runtime tool descriptor is already registered.")
        self._descriptors[descriptor.key] = descriptor

    def get(self, key: str) -> RuntimeToolDescriptor | None:
        return self._descriptors.get(validate_tool_key(key))

    def is_registered(self, key: str) -> bool:
        return self.get(key) is not None


runtime_tool_registry = RuntimeToolRegistry()
runtime_tool_registry.register(
    RuntimeToolDescriptor(
        key="dashboard.summary.read",
        implementation_name="Read dashboard summary",
        execution_mode="internal",
    )
)
runtime_tool_registry.register(
    RuntimeToolDescriptor(
        key="email.campaigns.list",
        implementation_name="List mock email campaigns",
        execution_mode="internal",
    )
)
