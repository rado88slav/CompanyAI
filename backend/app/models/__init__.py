"""Company AI database models.

Every SQLAlchemy model must be imported here so Alembic can discover its
metadata during automatic migration generation.
"""

from app.models.administrator import Administrator
from app.models.agent import Agent, AgentCredential, AgentCredentialStatus, AgentPermission, AgentPermissionStatus, AgentStatus, AgentType
from app.models.audit_log import (
    AuditAction,
    AuditActorType,
    AuditLog,
    AuditScope,
)
from app.models.company import Company, CompanyStatus
from app.models.company_setting import CompanySetting
from app.models.company_membership import CompanyMembership, CompanyRole

__all__ = [
    "Administrator",
    "Agent",
    "AgentCredential",
    "AgentCredentialStatus",
    "AgentPermission",
    "AgentPermissionStatus",
    "AgentStatus",
    "AgentType",
    "AuditAction",
    "AuditActorType",
    "AuditLog",
    "AuditScope",
    "Company",
    "CompanyMembership",
    "CompanyRole",
    "CompanySetting",
    "CompanyStatus",
]
from app.models.approval import ApprovalDecision, ApprovalRequest, AuthorizationPolicy, AuthorizationUsage

__all__ = ["ApprovalDecision", "ApprovalRequest", "AuthorizationPolicy", "AuthorizationUsage"]
from app.models.tool_registry import AgentToolGrant, AgentToolGrantStatus, CompanyTool, CompanyToolStatus, ToolDefinition, ToolExecutionMode, ToolRiskLevel, ToolStatus
from app.models.provider_connection import ProviderConnection, ProviderConnectionStatus, ProviderCredential, ProviderCredentialStatus
from app.models.provider_execution import ProviderExecution, ProviderExecutionAttempt
from app.models.email import EmailReplyProposal, InboundEmail, OutboundEmail

__all__ += ["AgentToolGrant", "AgentToolGrantStatus", "CompanyTool", "CompanyToolStatus", "ToolDefinition", "ToolExecutionMode", "ToolRiskLevel", "ToolStatus", "ProviderConnection", "ProviderConnectionStatus", "ProviderCredential", "ProviderCredentialStatus"]
__all__ += ["ProviderExecution", "ProviderExecutionAttempt"]
__all__ += ["EmailReplyProposal", "InboundEmail", "OutboundEmail"]
