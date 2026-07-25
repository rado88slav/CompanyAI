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
