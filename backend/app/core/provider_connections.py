"""Trusted provider descriptors and safe provider configuration validation."""

from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlsplit

PROVIDER_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
CAPABILITY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
FORBIDDEN_PARTS = frozenset({
    "password", "secret", "token", "api_key", "access_key", "private_key",
    "credential", "auth_token", "client_secret", "webhook_secret", "handler",
    "callable", "import", "import_path", "module", "source", "code", "script",
    "shell", "command", "executable", "subprocess",
})


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    key: str
    display_name: str
    category: str
    authentication_type: str
    required_secret_fields: frozenset[str]
    optional_secret_fields: frozenset[str]
    configuration_fields: frozenset[str]
    capabilities: frozenset[str]
    credentials_may_expire: bool = False

    def __post_init__(self) -> None:
        if not PROVIDER_KEY_PATTERN.fullmatch(self.key):
            raise ValueError("Provider key is invalid.")
        if self.required_secret_fields & self.configuration_fields or self.optional_secret_fields & self.configuration_fields:
            raise ValueError("Secret and configuration fields must not overlap.")
        if self.required_secret_fields & self.optional_secret_fields:
            raise ValueError("Required and optional secret fields must not overlap.")
        if not self.capabilities or any(not CAPABILITY_PATTERN.fullmatch(item) for item in self.capabilities):
            raise ValueError("Provider capability is invalid.")


class ProviderRegistry:
    def __init__(self) -> None:
        self._items: dict[str, ProviderDescriptor] = {}

    def register(self, descriptor: ProviderDescriptor) -> None:
        if descriptor.key in self._items:
            raise ValueError("Provider descriptor is already registered.")
        self._items[descriptor.key] = descriptor

    def get(self, key: str) -> ProviderDescriptor | None:
        if not isinstance(key, str) or not PROVIDER_KEY_PATTERN.fullmatch(key):
            return None
        return self._items.get(key)

    def require(self, key: str) -> ProviderDescriptor:
        item = self.get(key)
        if item is None:
            raise ValueError("Unknown provider key.")
        return item

    def all(self) -> tuple[ProviderDescriptor, ...]:
        return tuple(self._items[key] for key in sorted(self._items))

    @property
    def descriptors(self) -> Mapping[str, ProviderDescriptor]:
        return MappingProxyType(self._items)


def _descriptor(key: str, name: str, category: str, auth: str, required: set[str], *, optional: set[str] | None = None, config: set[str] | None = None, capabilities: set[str], expires: bool = False) -> ProviderDescriptor:
    return ProviderDescriptor(key, name, category, auth, frozenset(required), frozenset(optional or set()), frozenset(config or set()), frozenset(capabilities), expires)


provider_registry = ProviderRegistry()
for _item in (
    _descriptor("retell", "Retell", "voice_ai", "api_key", {"api_key"}, optional={"webhook_secret"}, capabilities={"voice.agent", "voice.call"}),
    _descriptor("twilio", "Twilio", "telephony", "account_credentials", {"account_sid", "auth_token"}, config={"region", "edge"}, capabilities={"telephony.call", "telephony.sms", "telephony.number"}),
    _descriptor("telnyx", "Telnyx", "telephony", "api_key", {"api_key"}, config={"connection_id"}, capabilities={"telephony.call", "telephony.sms", "telephony.number"}),
    _descriptor("microsoft_365", "Microsoft 365", "email", "oauth2_client_credentials", {"client_secret"}, config={"tenant_id", "client_id"}, capabilities={"email.send", "email.read", "email.reply"}, expires=True),
    _descriptor("google_workspace", "Google Workspace", "email", "service_account", {"service_account_json"}, config={"delegated_user"}, capabilities={"email.send", "email.read", "email.reply"}, expires=True),
    _descriptor("lemlist", "Lemlist", "outreach", "api_key", {"api_key"}, capabilities={"outreach.campaign", "outreach.contact", "email.campaign.read", "email.send"}),
    _descriptor("instantly", "Instantly", "outreach", "api_key", {"api_key"}, capabilities={"outreach.campaign", "outreach.contact", "email.send"}),
    _descriptor("smartlead", "Smartlead", "outreach", "api_key", {"api_key"}, capabilities={"outreach.campaign", "outreach.contact", "email.send"}),
    _descriptor(
        "generic_smtp_imap",
        "Generic SMTP/IMAP",
        "email",
        "username_password",
        {"password"},
        config={
            "email_address",
            "sender_display_name",
            "username",
            "smtp_host",
            "smtp_port",
            "smtp_security",
            "imap_host",
            "imap_port",
            "imap_security",
            "imap_folder",
            "reply_to_address",
        },
        capabilities={"email.send", "email.read", "email.reply"},
    ),
    _descriptor("local_test_email", "Local Test Email Provider", "email", "none", set(), capabilities={"email.send", "email.read", "email.reply"}),
    _descriptor("local_mock_email", "Local Mock Email Campaigns", "email", "none", set(), capabilities={"email.campaign.read"}),
):
    provider_registry.register(_item)


def validate_safe_object(value: object, *, allowed_fields: frozenset[str] | None = None, path: str = "value") -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be a JSON object.")
    if allowed_fields is not None and any(key not in allowed_fields for key in value):
        raise ValueError(f"{path} contains an unsupported field.")

    def walk(item: object, location: str) -> None:
        if isinstance(item, dict):
            folded: set[str] = set()
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError(f"{location} contains an invalid key.")
                lowered = key.casefold()
                if lowered in folded or lowered in FORBIDDEN_PARTS:
                    raise ValueError(f"{location} contains a forbidden field.")
                folded.add(lowered)
                if isinstance(child, str) and ("url" in lowered or "uri" in lowered):
                    parsed = urlsplit(child)
                    if parsed.username is not None or parsed.password is not None:
                        raise ValueError(f"{location} contains embedded URL credentials.")
                walk(child, f"{location}.{key}")
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{location}[{index}]")
        elif item is not None and not isinstance(item, (str, int, float, bool)):
            raise ValueError(f"{location} contains a non-JSON value.")

    walk(value, path)
    return value
