"""Central authorization modes, risk levels and safe default catalog."""

from enum import StrEnum


class AuthorizationMode(StrEnum):
    ASK_EVERY_TIME = "ask_every_time"
    APPROVE_SINGLE_ACTION = "approve_single_action"
    APPROVE_BATCH = "approve_batch"
    APPROVE_CAMPAIGN = "approve_campaign"
    APPROVE_UNTIL = "approve_until"
    ALLOW_WITHIN_LIMITS = "allow_within_limits"
    ALWAYS_REQUIRE_APPROVAL = "always_require_approval"
    BLOCK = "block"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyScopeType(StrEnum):
    """Reserved policy scope selectors; runtime actions must remain concrete."""

    ANY = "any"


RISK_ORDER = {level.value: index for index, level in enumerate(RiskLevel)}

ACTION_RISK_CATALOG: dict[str, RiskLevel] = {
    "metadata.read": RiskLevel.LOW,
    "crm.metadata.update": RiskLevel.MEDIUM,
    "email.message.send": RiskLevel.HIGH,
    "phone.call.initiate": RiskLevel.HIGH,
    "external.bulk_communication": RiskLevel.HIGH,
    "credential.mutate": RiskLevel.CRITICAL,
    "permission.change": RiskLevel.CRITICAL,
    "role.change": RiskLevel.CRITICAL,
    "owner.change": RiskLevel.CRITICAL,
    "resource.delete_irreversible": RiskLevel.CRITICAL,
    "financial.execute": RiskLevel.CRITICAL,
    "shell.destructive": RiskLevel.CRITICAL,
}


def resolve_platform_risk(action_type: str) -> RiskLevel:
    """Resolve fail-safe platform risk; unknown actions are high risk."""

    return ACTION_RISK_CATALOG.get(action_type, RiskLevel.HIGH)


def max_risk(first: str, second: str) -> RiskLevel:
    """Return the higher risk without allowing a downgrade."""

    return RiskLevel(first if RISK_ORDER[first] >= RISK_ORDER[second] else second)
