import { companyApi } from "./client";
import type { AgentRuntimeResult, AgentRuntimeTool } from "../types/agentRuntime";

export const agentRuntimeApi = {
  tools: (signal?: AbortSignal) =>
    companyApi<{ items: AgentRuntimeTool[] }>("/agent-runtime/tools", { signal }),
  setupDashboardSummaryTool: () =>
    companyApi<{ tool_key: string; company_enabled: boolean }>(
      "/agent-runtime/tools/dashboard-summary/setup",
      { method: "POST" },
    ),
  invoke: (toolKey: string) =>
    companyApi<AgentRuntimeResult>(
      `/agent-runtime/tools/${encodeURIComponent(toolKey)}/invoke`,
      { method: "POST", body: JSON.stringify({ input: {} }) },
    ),
};
