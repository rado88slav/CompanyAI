export type AgentRuntimeTool = {
  key: string;
  display_name: string;
  description: string;
  category: string;
  risk_level: string;
  requires_approval: boolean;
  runtime_registered: boolean;
  company_enabled: boolean;
};

export type AgentRuntimeResult = {
  tool_key: string;
  status: string;
  executed_at: string;
  audit_event_id: string;
  result: {
    service?: {
      status?: string;
      readiness?: string;
      environment?: string;
      version?: string;
    };
    counts?: Record<string, number>;
    recent_audit_events?: Array<{
      id: string;
      actor_type: string;
      action: string;
      resource_type: string;
      resource_id: string | null;
      created_at: string;
    }>;
    items?: Array<Record<string, unknown>>;
    total?: number;
    limit?: number;
    offset?: number;
  };
};
