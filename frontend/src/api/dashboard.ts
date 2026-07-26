import type {
  DashboardAuditEvent,
  DashboardCounts,
  DashboardSummary,
} from "../types/dashboard";
import { ApiError, accessToken, companyId, notifySessionExpired } from "./client";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonNegativeNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function isCounts(value: unknown): value is DashboardCounts {
  if (!isRecord(value)) return false;
  return [
    "provider_connections",
    "enabled_provider_connections",
    "provider_credentials",
    "pending_approvals",
    "provider_executions",
    "failed_provider_executions",
    "audit_events",
  ].every((field) => isNonNegativeNumber(value[field]));
}

function isAuditEvent(value: unknown): value is DashboardAuditEvent {
  if (!isRecord(value)) return false;
  return (
    typeof value.id === "string" &&
    ["administrator", "agent", "system"].includes(String(value.actor_type)) &&
    typeof value.action === "string" &&
    typeof value.resource_type === "string" &&
    (value.resource_id === null || typeof value.resource_id === "string") &&
    typeof value.created_at === "string"
  );
}

function isDashboardSummary(value: unknown): value is DashboardSummary {
  if (!isRecord(value) || !isRecord(value.service)) return false;
  return (
    value.service.status === "ok" &&
    value.service.readiness === "reachable" &&
    typeof value.service.environment === "string" &&
    typeof value.service.version === "string" &&
    isCounts(value.counts) &&
    Array.isArray(value.recent_audit_events) &&
    value.recent_audit_events.every(isAuditEvent)
  );
}

export async function fetchDashboardSummary(
  signal?: AbortSignal,
): Promise<DashboardSummary> {
  const token = accessToken();
  const id = companyId();

  if (!token || !id) {
    throw new Error(
      "An authenticated company context is required to load the dashboard.",
    );
  }

  const response = await fetch(
    `/api/v1/companies/${encodeURIComponent(id)}/dashboard/summary`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Company-ID": id,
      },
      signal,
    },
  );

  if (!response.ok) {
    if (response.status === 401 || response.status === 403) notifySessionExpired();
    throw new ApiError("The dashboard summary is currently unavailable.", response.status);
  }

  const payload: unknown = await response.json();
  if (!isDashboardSummary(payload)) {
    throw new Error("The dashboard returned an invalid response.");
  }
  return payload;
}
