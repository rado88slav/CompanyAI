import { companyApi } from "./client";
import type { EmailApproval, EmailCampaign, InboundEmail, InboundEmailDetail, OutboundEmail, ReplyProposal } from "../types/email";
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
  connections: () => companyApi<{items: Array<{id: string; provider_key: string; status: string}>}>("/provider-connections"),
  campaigns: () => companyApi<{items: EmailCampaign[]; total: number}>("/email-campaigns"),
};
