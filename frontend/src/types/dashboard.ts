export interface DashboardService {
  status: "ok";
  readiness: "reachable";
  environment: string;
  version: string;
}

export interface DashboardCounts {
  provider_connections: number;
  enabled_provider_connections: number;
  provider_credentials: number;
  pending_approvals: number;
  provider_executions: number;
  failed_provider_executions: number;
  audit_events: number;
}

export interface DashboardAuditEvent {
  id: string;
  actor_type: "administrator" | "agent" | "system";
  action: string;
  resource_type: string;
  resource_id: string | null;
  created_at: string;
}

export interface DashboardSummary {
  service: DashboardService;
  counts: DashboardCounts;
  recent_audit_events: DashboardAuditEvent[];
}
