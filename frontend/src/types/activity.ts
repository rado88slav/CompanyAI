export type ActivityEvent = {
  id: string;
  company_id: string;
  occurred_at: string;
  category: "agent" | "approval" | "provider" | "email" | "system" | string;
  source: string;
  action: string;
  title: string;
  summary: string;
  status: string;
  severity: "info" | "warning" | "error" | string;
  actor_display: string;
  entity_type: string;
  entity_id: string | null;
  safe_details: Record<string, string | number | boolean | null>;
  correlation_id: string | null;
};

export type ActivityEventList = {
  items: ActivityEvent[];
  total: number;
  limit: number;
  offset: number;
};

export type ActivityFilters = {
  source?: string;
  severity?: string;
  actor?: string;
  event_type?: string;
  limit?: number;
  offset?: number;
};
