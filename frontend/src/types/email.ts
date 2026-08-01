export type ReplyProposal = {
  id: string; recipient_email: string; subject: string; body: string;
  status: string; approval_request_id: string | null;
};
export type OutboundEmail = {
  id: string; provider_execution_id: string; status: string;
  provider_message_id: string | null; sent_at: string | null;
};
export type InboundEmail = {
  id: string; sender_name: string | null; sender_email: string;
  recipient_email: string; subject: string; received_at: string; status: string;
  proposal_status: string | null; approval_status: string | null; send_status: string | null;
};
export type InboundEmailDetail = InboundEmail & {
  external_message_id: string; body: string; created_at: string; updated_at: string;
  reply_proposal: ReplyProposal | null; outbound_email: OutboundEmail | null;
};
export type EmailApproval = {
  id: string; status: string; requester_administrator_id: string | null; created_at: string;
  recipient_email: string; subject: string; body: string; inbound_email_id: string;
  inbound_subject: string; requested_action: string;
};
export type AuditEvent = {
  id: string; actor_type: string; actor_administrator_id: string | null;
  action: string; resource_type: string; resource_id: string | null; created_at: string;
};
export type EmailCampaign = {
  id: string; company_id: string; provider_key: string; external_campaign_id: string;
  name: string; status: string; audience_count: number; sent_count: number;
  reply_count: number; bounce_count: number; created_at: string; updated_at: string;
};

export type SendWindow = { start: string; end: string };

export type FollowUpStep = {
  step_number: number;
  delay_amount: number;
  delay_unit: "calendar_days" | "business_days";
  template_reference: string;
  stop_on_reply: boolean;
  stop_on_unsubscribe: boolean;
  stop_on_hard_bounce: boolean;
  stop_on_manual_block: boolean;
};

export type CampaignScheduleSettings = {
  campaign_key: string;
  status: string;
  timezone: string;
  allowed_weekdays: number[];
  send_windows: SendWindow[];
  randomized_timing: {
    minimum_delay_minutes: number;
    maximum_delay_minutes: number;
    jitter_minutes: number;
  };
  limits: {
    campaign_hourly: number;
    campaign_daily: number;
    mailbox_hourly: number;
    mailbox_daily: number;
    mailbox_max_consecutive: number;
    company_daily: number | null;
  };
  mailbox_rotation: {
    strategy: "round_robin" | "random" | "preferred_with_fallback";
    allowed_connection_ids: string[];
    preferred_connection_id: string | null;
    reply_monitoring_required: boolean;
    paused_connection_ids: string[];
  };
  follow_up_steps: FollowUpStep[];
  maximum_follow_ups: number;
  start_date: string | null;
  end_date: string | null;
  approval_mode: "draft_only" | "campaign" | "batch" | "period" | "mailboxes" | "per_action";
  auto_pause: {
    authentication_failures: number;
    tls_or_connection_failures: number;
    provider_quota_reached: boolean;
    hourly_or_daily_limit_reached: boolean;
    bounce_rate_percent: number;
    unsubscribe_received: boolean;
    missing_mailbox: boolean;
    approval_unavailable: boolean;
    internal_error: boolean;
  };
  pause_reason: string | null;
  worker_enabled: boolean;
};

export type CampaignSchedulePreviewSlot = {
  sequence: number;
  planned_at_utc: string | null;
  planned_at_local: string | null;
  timezone: string;
  mailbox_connection_id: string | null;
  mailbox_display_name: string | null;
  campaign_key: string;
  recipient_step: string;
  status: string;
  reason: string | null;
  applicable_limits: Record<string, number | null>;
};

export type CampaignSchedulePreview = {
  settings: CampaignScheduleSettings;
  slots: CampaignSchedulePreviewSlot[];
  skipped: CampaignSchedulePreviewSlot[];
  worker_enabled: boolean;
  worker_contract: Record<string, string | boolean>;
};

export type SingleMessageTestPayload = {
  provider_connection_id: string;
  recipient_email: string;
  subject: string;
  body: string;
  idempotency_key: string;
  mode?: "simulation" | "live_test";
};

export type SingleMessagePreview = SingleMessageTestPayload & {
  sender_email: string;
  payload_digest: string;
  approval_required: boolean;
  simulation_only: boolean;
  live_send_available: boolean;
  disabled_features: string[];
  mode: "simulation" | "live_test";
};

export type SingleMessageApproval = SingleMessagePreview & {
  provider_execution_id: string;
  approval_request_id: string;
  status: string;
};

export type SingleMessageSimulation = {
  provider_execution_id: string;
  status: string;
  result_metadata: Record<string, string | boolean>;
  simulation_only: boolean;
  external_action_taken: boolean;
};

export type SingleMessageLiveExecution = SingleMessageSimulation;

export type SingleMessageRecipientAllowlist = {
  recipient_allowlist: string[];
  exact_only: boolean;
};

export type WorkerSimulation = {
  simulation_only: boolean;
  worker_enabled: boolean;
  status: string;
  idempotency_key: string;
  would_execute: CampaignSchedulePreviewSlot[];
  skipped: CampaignSchedulePreviewSlot[];
  external_action_taken: boolean;
  provider_execution_created: boolean;
  audit_recorded: boolean;
};
