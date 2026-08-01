import { companyApi } from "./client";
import type { AgentPreviewTaskKey, AgentPreviewTaskResult, AgentTemplate, ManagedAgent, PromptPreview } from "../types/agentManager";

export const agentManagerApi = {
  templates: (signal?: AbortSignal) => companyApi<AgentTemplate[]>("/agent-manager/templates", { signal }),
  agents: (signal?: AbortSignal) => companyApi<{items: ManagedAgent[]; total: number}>("/agent-manager/agents", { signal }),
  createFromTemplate: (companyInstructions: string) =>
    companyApi<ManagedAgent>("/agent-manager/agents/from-template", {
      method: "POST",
      body: JSON.stringify({ template_id: "email_operations_preview_agent", company_instructions: companyInstructions }),
    }),
  updateInstructions: (agentId: string, companyInstructions: string) =>
    companyApi<ManagedAgent>(`/agent-manager/agents/${encodeURIComponent(agentId)}/instructions`, {
      method: "PATCH",
      body: JSON.stringify({ company_instructions: companyInstructions }),
    }),
  activate: (agentId: string) =>
    companyApi<ManagedAgent>(`/agent-manager/agents/${encodeURIComponent(agentId)}/activate`, { method: "POST" }),
  deactivate: (agentId: string) =>
    companyApi<ManagedAgent>(`/agent-manager/agents/${encodeURIComponent(agentId)}/deactivate`, { method: "POST" }),
  promptPreview: (agentId: string) =>
    companyApi<PromptPreview>(`/agent-manager/agents/${encodeURIComponent(agentId)}/prompt-preview`),
  runTask: (agentId: string, taskKey: AgentPreviewTaskKey) =>
    companyApi<AgentPreviewTaskResult>(`/agent-manager/agents/${encodeURIComponent(agentId)}/preview-task`, {
      method: "POST",
      body: JSON.stringify({ task_key: taskKey }),
    }),
};
