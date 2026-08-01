import { companyApi } from "./client";
import type { CampaignSchedulePreview, CampaignScheduleSettings, EmailApproval, EmailCampaign, InboundEmail, InboundEmailDetail, OutboundEmail, ReplyProposal, SingleMessageApproval, SingleMessageLiveExecution, SingleMessagePreview, SingleMessageRecipientAllowlist, SingleMessageTestPayload, SingleMessageSimulation, WorkerSimulation } from "../types/email";
import type { ActivityEventList } from "../types/activity";

export const emailApi = {
  list: () => companyApi<{items: InboundEmail[]}>("/emails"),
  detail: (id: string) => companyApi<InboundEmailDetail>(`/emails/${encodeURIComponent(id)}`),
  createProposal: (emailId: string, data: {recipient_email: string; subject: string; body: string}) =>
    companyApi<ReplyProposal>(`/emails/${encodeURIComponent(emailId)}/reply-proposals`, {method: "POST", body: JSON.stringify(data)}),
  updateProposal: (id: string, data: {recipient_email: string; subject: string; body: string}) =>
    companyApi<ReplyProposal>(`/reply-proposals/${encodeURIComponent(id)}`, {method: "PATCH", body: JSON.stringify(data)}),
  submit: (id: string) => companyApi<ReplyProposal>(`/reply-proposals/${encodeURIComponent(id)}/submit`, {method: "POST"}),
  send: (id: string, providerConnectionId: string) =>
    companyApi<OutboundEmail>(`/reply-proposals/${encodeURIComponent(id)}/send`, {method: "POST", body: JSON.stringify({provider_connection_id: providerConnectionId})}),
  approvals: () => companyApi<{items: EmailApproval[]}>("/email-approvals"),
  approve: (id: string) => companyApi(`/email-approvals/${encodeURIComponent(id)}/approve`, {method: "POST"}),
  deny: (id: string) => companyApi(`/email-approvals/${encodeURIComponent(id)}/reject`, {method: "POST"}),
  audit: () => companyApi<ActivityEventList>("/activity"),
  connections: () => companyApi<{items: Array<{id: string; provider_key: string; display_name: string; status: string}>}>("/provider-connections"),
  campaigns: () => companyApi<{items: EmailCampaign[]; total: number}>("/email-campaigns"),
  schedule: () => companyApi<CampaignScheduleSettings>("/email-automation/schedule"),
  saveSchedule: (data: CampaignScheduleSettings) => companyApi<CampaignScheduleSettings>("/email-automation/schedule", {method: "PUT", body: JSON.stringify(data)}),
  previewSchedule: (recipientCount: number) => companyApi<CampaignSchedulePreview>("/email-automation/schedule/preview", {method: "POST", body: JSON.stringify({recipient_count: recipientCount, include_follow_ups: true})}),
  pauseSchedule: (reason = "manual") => companyApi<CampaignScheduleSettings>("/email-automation/schedule/pause", {method: "POST", body: JSON.stringify({reason})}),
  resumeSchedule: () => companyApi<CampaignScheduleSettings>("/email-automation/schedule/resume", {method: "POST"}),
  previewSingleMessage: (data: SingleMessageTestPayload) =>
    companyApi<SingleMessagePreview>("/emails/single-message-tests/preview", {method: "POST", body: JSON.stringify(data)}),
  requestSingleMessageApproval: (data: SingleMessageTestPayload) =>
    companyApi<SingleMessageApproval>("/emails/single-message-tests/request-approval", {method: "POST", body: JSON.stringify({...data, confirmation_text: "CONFIRM ONE TEST EMAIL"})}),
  executeSingleMessageSimulation: (providerExecutionId: string) =>
    companyApi<SingleMessageSimulation>("/emails/single-message-tests/execute-simulation", {method: "POST", body: JSON.stringify({provider_execution_id: providerExecutionId, confirmation_text: "CONFIRM SIMULATION ONLY"})}),
  executeSingleMessageLive: (providerExecutionId: string, subject: string, body: string) =>
    companyApi<SingleMessageLiveExecution>("/emails/single-message-tests/execute-live", {method: "POST", body: JSON.stringify({provider_execution_id: providerExecutionId, subject, body, confirmation_text: "SEND ONE TEST EMAIL"})}),
  singleMessageRecipientAllowlist: () =>
    companyApi<SingleMessageRecipientAllowlist>("/emails/single-message-tests/recipient-allowlist"),
  addSingleMessageRecipientAllowlist: (recipientEmail: string) =>
    companyApi<SingleMessageRecipientAllowlist>("/emails/single-message-tests/recipient-allowlist", {method: "POST", body: JSON.stringify({recipient_email: recipientEmail})}),
  simulateWorker: () =>
    companyApi<WorkerSimulation>("/email-automation/worker/simulate", {method: "POST", body: JSON.stringify({max_actions: 10, idempotency_key: `worker-sim-${Date.now()}`})}),
};
