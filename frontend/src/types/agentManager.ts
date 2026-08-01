export type AgentTemplate = {
  template_id: string;
  name: string;
  role: string;
  runtime_type: string;
  approval_mode: string;
  allowed_tools: string[];
  forbidden_actions: string[];
  default_permissions: string[];
};

export type ManagedAgent = {
  id: string;
  company_id: string;
  name: string;
  slug: string;
  role: string;
  status: string;
  runtime_type: string;
  assigned_tools: string[];
  permissions: string[];
  approval_mode: string;
  health: string;
  readiness: string;
  last_activity_at: string | null;
  instructions: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type PromptPreview = {
  agent_id: string;
  template_id: string;
  sections: Record<string, unknown>;
  prompt_text: string;
};

export type AgentPreviewTaskKey =
  | "preview_next_email_actions"
  | "draft_interested_follow_up"
  | "classify_unsubscribe"
  | "propose_campaign_pause"
  | "attempt_forbidden_send";

export type AgentPreviewTaskResult = {
  agent_id: string;
  task_key: string;
  runtime_type: string;
  status: string;
  proposal: {
    proposal_type: string;
    summary: string;
    recommended_action: string;
    draft_subject: string | null;
    draft_body: string | null;
    classification: string | null;
    safety_notes: string[];
  };
  authorization: {
    status: string;
    reason_code: string;
    effective_risk: string;
    approval_request_id: string | null;
    policy_id: string | null;
  };
  audit_event_id: string;
  provider_execution_created: boolean;
  external_action_taken: boolean;
};
