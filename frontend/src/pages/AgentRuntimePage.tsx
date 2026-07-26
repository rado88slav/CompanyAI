import { useCallback, useEffect, useState } from "react";

import { agentRuntimeApi } from "../api/agentRuntime";
import type { AgentRuntimeResult, AgentRuntimeTool } from "../types/agentRuntime";

function CountGrid({ counts }: { counts: Record<string, number> }) {
  return (
    <div className="compact-metrics">
      {Object.entries(counts).map(([key, value]) => (
        <div className="compact-metric" key={key}>
          <span>{key.replaceAll("_", " ")}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </div>
  );
}

export function AgentRuntimePage() {
  const [tools, setTools] = useState<AgentRuntimeTool[]>([]);
  const [result, setResult] = useState<AgentRuntimeResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const response = await agentRuntimeApi.tools(signal);
      setTools(response.items);
      setError("");
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      setError("Agent runtime tools are currently unavailable.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function setupTool() {
    setBusy("setup");
    try {
      await agentRuntimeApi.setupDashboardSummaryTool();
      await load();
      setError("");
    } catch {
      setError("The local read-only tool could not be prepared.");
    } finally {
      setBusy("");
    }
  }

  async function invokeTool(tool: AgentRuntimeTool) {
    setBusy(tool.key);
    try {
      setResult(await agentRuntimeApi.invoke(tool.key));
      setError("");
    } catch {
      setError("The agent runtime could not complete the read-only request.");
    } finally {
      setBusy("");
    }
  }

  if (loading) {
    return (
      <section className="page">
        <div className="state-panel">
          <span className="spinner" aria-hidden="true" />
          <div>
            <h2>Loading agent runtime</h2>
            <p>Reading company-scoped runtime tools.</p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="page">
      <div className="page-heading page-heading--split">
        <div>
          <span className="eyebrow">Operational agent</span>
          <h1>Agent Activity</h1>
          <p>Run deterministic internal tools through the controlled runtime boundary.</p>
        </div>
        <button className="button" type="button" onClick={() => void load()}>
          Refresh
        </button>
      </div>

      {error && <p role="alert" className="error-text">{error}</p>}

      {tools.length === 0 ? (
        <div className="state-panel">
          <div>
            <h2>No runtime tools enabled</h2>
            <p>The local read-only dashboard summary tool is not enabled for this company.</p>
          </div>
          <button className="button" type="button" disabled={busy === "setup"} onClick={() => void setupTool()}>
            Enable local tool
          </button>
        </div>
      ) : (
        <div className="provider-grid">
          {tools.map((tool) => (
            <article className="provider-card" key={tool.key}>
              <div className="provider-card__header">
                <div>
                  <h3>{tool.display_name}</h3>
                  <p>{tool.description}</p>
                </div>
                <span className="status-badge status-badge--neutral">
                  {tool.company_enabled ? "enabled" : "disabled"}
                </span>
              </div>
              <dl className="detail-list">
                <div><dt>Tool key</dt><dd>{tool.key}</dd></div>
                <div><dt>Category</dt><dd>{tool.category}</dd></div>
                <div><dt>Risk</dt><dd>{tool.risk_level}</dd></div>
                <div><dt>Approval</dt><dd>{tool.requires_approval ? "Required" : "Not required"}</dd></div>
              </dl>
              <button className="button" type="button" disabled={!tool.company_enabled || busy === tool.key} onClick={() => void invokeTool(tool)}>
                Run read-only tool
              </button>
            </article>
          ))}
        </div>
      )}

      {result && (
        <section className="activity-panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Structured result</span>
              <h2>{result.tool_key}</h2>
            </div>
            <span className="status-badge status-badge--positive">{result.status}</span>
          </div>
          <dl className="detail-list">
            <div><dt>Executed</dt><dd>{new Date(result.executed_at).toLocaleString()}</dd></div>
            <div><dt>Audit event</dt><dd>{result.audit_event_id}</dd></div>
            <div><dt>Service</dt><dd>{result.result.service?.status ?? "Unknown"}</dd></div>
            <div><dt>Readiness</dt><dd>{result.result.service?.readiness ?? "Unknown"}</dd></div>
          </dl>
          {result.result.counts && <CountGrid counts={result.result.counts} />}
          {result.result.items && (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Name</th><th>Status</th><th>Provider</th><th>Total</th></tr></thead>
                <tbody>
                  {result.result.items.map((item, index) => (
                    <tr key={String(item.id ?? index)}>
                      <td>{String(item.name ?? "Untitled")}</td>
                      <td>{String(item.status ?? "unknown")}</td>
                      <td>{String(item.provider_key ?? "internal")}</td>
                      <td>{String(item.audience_count ?? "")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </section>
  );
}
