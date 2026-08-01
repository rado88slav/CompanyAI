import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { agentManagerApi } from "../api/agentManager";
import type { AgentPreviewTaskKey, AgentPreviewTaskResult, AgentTemplate, ManagedAgent, PromptPreview } from "../types/agentManager";

const tasks: Array<{ key: AgentPreviewTaskKey; label: string }> = [
  { key: "preview_next_email_actions", label: "Preview the next 10 scheduled email actions" },
  { key: "draft_interested_follow_up", label: "Draft a follow-up for a synthetic interested reply" },
  { key: "classify_unsubscribe", label: "Classify a synthetic unsubscribe reply" },
  { key: "propose_campaign_pause", label: "Propose pausing a synthetic campaign" },
  { key: "attempt_forbidden_send", label: "Attempt a forbidden send action" },
];

function ChipList({ values }: { values: string[] }) {
  return <div className="chip-list">{values.map((value) => <span className="chip" key={value}>{value}</span>)}</div>;
}

export function AgentRuntimePage() {
  const [templates, setTemplates] = useState<AgentTemplate[]>([]);
  const [agents, setAgents] = useState<ManagedAgent[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [prompt, setPrompt] = useState<PromptPreview | null>(null);
  const [result, setResult] = useState<AgentPreviewTaskResult | null>(null);
  const [instructions, setInstructions] = useState("Use conservative, preview-only recommendations.");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const selectedAgent = useMemo(() => agents.find((agent) => agent.id === selectedAgentId) ?? agents[0] ?? null, [agents, selectedAgentId]);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const [templateValue, agentValue] = await Promise.all([
        agentManagerApi.templates(signal),
        agentManagerApi.agents(signal),
      ]);
      setTemplates(templateValue);
      setAgents(agentValue.items);
      setSelectedAgentId((current) => current || agentValue.items[0]?.id || "");
      setError("");
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      setError("AI Agents are currently unavailable.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function createAgent() {
    setBusy("create");
    try {
      const agent = await agentManagerApi.createFromTemplate(instructions);
      setAgents((items) => [agent, ...items.filter((item) => item.id !== agent.id)]);
      setSelectedAgentId(agent.id);
      setError("");
    } catch {
      setError("The Email Operations Preview Agent could not be created.");
    } finally {
      setBusy("");
    }
  }

  async function saveInstructions(agent: ManagedAgent) {
    setBusy("instructions");
    try {
      const updated = await agentManagerApi.updateInstructions(agent.id, instructions);
      setAgents((items) => items.map((item) => item.id === updated.id ? updated : item));
      setError("");
    } catch {
      setError("Instructions could not be saved.");
    } finally {
      setBusy("");
    }
  }

  async function setActive(agent: ManagedAgent, active: boolean) {
    setBusy(active ? "activate" : "deactivate");
    try {
      const updated = active ? await agentManagerApi.activate(agent.id) : await agentManagerApi.deactivate(agent.id);
      setAgents((items) => items.map((item) => item.id === updated.id ? updated : item));
      setError("");
    } catch {
      setError("Agent status could not be changed.");
    } finally {
      setBusy("");
    }
  }

  async function previewPrompt(agent: ManagedAgent) {
    setBusy("prompt");
    try {
      setPrompt(await agentManagerApi.promptPreview(agent.id));
      setError("");
    } catch {
      setError("Prompt preview could not be loaded.");
    } finally {
      setBusy("");
    }
  }

  async function runTask(agent: ManagedAgent, taskKey: AgentPreviewTaskKey) {
    setBusy(taskKey);
    try {
      setResult(await agentManagerApi.runTask(agent.id, taskKey));
      setError("");
    } catch {
      setError("Preview task could not be completed.");
    } finally {
      setBusy("");
    }
  }

  if (loading) {
    return <section className="page"><div className="state-panel"><span className="spinner" aria-hidden="true" /><div><h2>Loading AI Agents</h2><p>Reading safe preview agents for the active company.</p></div></div></section>;
  }

  return (
    <section className="page">
      <div className="page-heading page-heading--split">
        <div>
          <span className="eyebrow">Safe preview runtime</span>
          <h1>AI Agents</h1>
          <p>Create and test preview-only agents without external actions, credentials or unrestricted tools.</p>
        </div>
        <div className="heading-actions">
          <Link className="button button--light" to="/documentation/ai-agents">AI Agent Guide</Link>
          <button className="button button--light" type="button" onClick={() => void load()}>Refresh</button>
        </div>
      </div>

      {error && <p role="alert" className="error-text">{error}</p>}

      <section className="agent-manager-layout">
        <div className="agent-template-panel">
          <span className="eyebrow">Built-in template</span>
          <h2>Email Operations Preview Agent</h2>
          <p>Inspects safe campaign and mailbox metadata, drafts synthetic responses and proposes pauses. It cannot send email.</p>
          {templates[0] && <dl className="detail-list">
            <div><dt>Runtime</dt><dd>{templates[0].runtime_type}</dd></div>
            <div><dt>Approval</dt><dd>{templates[0].approval_mode}</dd></div>
          </dl>}
          <label>Company instructions
            <textarea value={instructions} maxLength={2000} onChange={(event) => setInstructions(event.target.value)} />
          </label>
          <button className="button" type="button" disabled={busy === "create"} onClick={() => void createAgent()}>Create preview agent</button>
        </div>

        <div className="agent-list-panel">
          <div className="section-heading"><div><span className="eyebrow">Registered agents</span><h2>Company agents</h2></div></div>
          {agents.length === 0 ? <div className="activity-empty"><p>No AI Agents are registered for this company yet.</p></div> : (
            <div className="provider-grid">
              {agents.map((agent) => (
                <article className={`provider-card ${selectedAgent?.id === agent.id ? "is-selected" : ""}`} key={agent.id}>
                  <div className="provider-card__header"><div><h3>{agent.name}</h3><p>{agent.role}</p></div><span className="status-badge status-badge--neutral">{agent.status}</span></div>
                  <dl className="detail-list">
                    <div><dt>Runtime</dt><dd>{agent.runtime_type}</dd></div>
                    <div><dt>Readiness</dt><dd>{agent.readiness}</dd></div>
                    <div><dt>Last activity</dt><dd>{agent.last_activity_at ? new Date(agent.last_activity_at).toLocaleString() : "Never"}</dd></div>
                  </dl>
                  <ChipList values={agent.permissions} />
                  <div className="actions">
                    <button className="button button--light" type="button" onClick={() => setSelectedAgentId(agent.id)}>Select</button>
                    <button className="button button--light" type="button" onClick={() => void previewPrompt(agent)}>Prompt preview</button>
                    <button className="button" type="button" disabled={busy === "activate" || agent.status === "active"} onClick={() => void setActive(agent, true)}>Activate</button>
                    <button className="button button--light" type="button" disabled={busy === "deactivate" || agent.status !== "active"} onClick={() => void setActive(agent, false)}>Deactivate</button>
                  </div>
                  <button className="button button--light" type="button" disabled={busy === "instructions"} onClick={() => void saveInstructions(agent)}>Save instructions</button>
                </article>
              ))}
            </div>
          )}
        </div>
      </section>

      {selectedAgent && <section className="activity-panel">
        <div className="section-heading"><div><span className="eyebrow">Synthetic tasks</span><h2>{selectedAgent.name}</h2></div><span className="status-badge status-badge--neutral">{selectedAgent.approval_mode}</span></div>
        <div className="agent-task-grid">
          {tasks.map((task) => <button className="button button--light" key={task.key} type="button" disabled={selectedAgent.status !== "active" || busy === task.key} onClick={() => void runTask(selectedAgent, task.key)}>{task.label}</button>)}
        </div>
      </section>}

      {prompt && <section className="activity-panel">
        <div className="section-heading"><div><span className="eyebrow">Effective instructions</span><h2>Prompt preview</h2></div></div>
        <pre className="prompt-preview">{prompt.prompt_text}</pre>
      </section>}

      {result && <section className="activity-panel">
        <div className="section-heading"><div><span className="eyebrow">Preview result</span><h2>{result.proposal.proposal_type}</h2></div><span className="status-badge status-badge--neutral">{result.status}</span></div>
        <dl className="detail-list">
          <div><dt>Authorization</dt><dd>{result.authorization.status}</dd></div>
          <div><dt>Reason</dt><dd>{result.authorization.reason_code}</dd></div>
          <div><dt>Risk</dt><dd>{result.authorization.effective_risk}</dd></div>
          <div><dt>Audit event</dt><dd>{result.audit_event_id}</dd></div>
          <div><dt>External action</dt><dd>{result.external_action_taken ? "yes" : "no"}</dd></div>
        </dl>
        <p>{result.proposal.summary}</p>
        <p><strong>{result.proposal.recommended_action}</strong></p>
        {result.proposal.draft_subject && <div className="state-card"><h3>{result.proposal.draft_subject}</h3><p>{result.proposal.draft_body}</p></div>}
        <ChipList values={result.proposal.safety_notes} />
      </section>}
    </section>
  );
}
