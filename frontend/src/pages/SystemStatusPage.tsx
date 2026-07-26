import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchDashboardSummary } from "../api/dashboard";
import { useActiveCompany } from "../context/ActiveCompanyContext";
import type { DashboardSummary } from "../types/dashboard";

type StatusTone = "green" | "yellow" | "red";

interface StatusItem {
  name: string;
  status: string;
  detail: string;
  tone: StatusTone;
}

function toneLabel(tone: StatusTone) {
  if (tone === "green") return "Healthy";
  if (tone === "yellow") return "Limited";
  return "Attention";
}

function buildStatusItems(summary: DashboardSummary): StatusItem[] {
  const hasProviders = summary.counts.provider_connections > 0;
  const hasActiveProviders = summary.counts.enabled_provider_connections > 0;
  const hasFailedExecutions = summary.counts.failed_provider_executions > 0;

  return [
    {
      name: "Backend",
      status: "Online",
      detail: `${summary.service.environment} runtime, version ${summary.service.version}`,
      tone: summary.service.status === "ok" ? "green" : "red",
    },
    {
      name: "Database",
      status: summary.service.readiness === "reachable" ? "Reachable" : "Unavailable",
      detail: "Primary PostgreSQL application store",
      tone: summary.service.readiness === "reachable" ? "green" : "red",
    },
    {
      name: "Queue",
      status: "Not provisioned",
      detail: "Background queue is not part of the current local MVP runtime",
      tone: "yellow",
    },
    {
      name: "Storage",
      status: "Protected",
      detail: "Dashboard exposes no credential payloads, keys or secret values",
      tone: "green",
    },
    {
      name: "Providers",
      status: hasActiveProviders ? "Active" : hasProviders ? "Configured" : "Setup needed",
      detail: `${summary.counts.enabled_provider_connections}/${summary.counts.provider_connections} provider connections enabled`,
      tone: hasActiveProviders ? "green" : "yellow",
    },
    {
      name: "Agent Runtime",
      status: hasFailedExecutions ? "Needs review" : "Read-only",
      detail: `${summary.counts.provider_executions} executions recorded, ${summary.counts.failed_provider_executions} failed`,
      tone: hasFailedExecutions ? "yellow" : "green",
    },
    {
      name: "Lemlist",
      status: "Read-only contract",
      detail: "Adapter contract is available; live credentials are not configured",
      tone: "yellow",
    },
    {
      name: "Future Telephony",
      status: "Planned",
      detail: "No call placement or paid telephony action is enabled",
      tone: "yellow",
    },
    {
      name: "Future AI Providers",
      status: "Planned",
      detail: "No external AI provider credential is configured in this dashboard",
      tone: "yellow",
    },
  ];
}

function StatusCard({ item }: { item: StatusItem }) {
  return (
    <article className={`system-status-card system-status-card--${item.tone}`}>
      <div className="system-status-card__heading">
        <span className={`health-dot health-dot--${item.tone}`} aria-hidden="true" />
        <span>{toneLabel(item.tone)}</span>
      </div>
      <h2>{item.name}</h2>
      <strong>{item.status}</strong>
      <p>{item.detail}</p>
    </article>
  );
}

export function SystemStatusPage() {
  const activeCompany = useActiveCompany();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [requestVersion, setRequestVersion] = useState(0);

  const refresh = useCallback(() => {
    setRequestVersion((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setState("loading");
    fetchDashboardSummary(controller.signal)
      .then((value) => {
        setSummary(value);
        setState("ready");
      })
      .catch((error) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setSummary(null);
        setState("error");
      });
    return () => controller.abort();
  }, [requestVersion]);

  const items = useMemo(() => (summary ? buildStatusItems(summary) : []), [summary]);
  const attentionCount = items.filter((item) => item.tone !== "green").length;

  return (
    <section className="page system-status" aria-labelledby="system-status-title">
      <div className="overview-hero system-status-hero">
        <div>
          <span className="eyebrow">System Status</span>
          <h1 id="system-status-title">Operational health without the noise.</h1>
          <p>
            Read-only service indicators for{" "}
            <strong>{activeCompany?.company.name ?? "the active company"}</strong>.
          </p>
        </div>
        <button className="button" type="button" onClick={refresh} disabled={state === "loading"}>
          Refresh
        </button>
      </div>

      {state === "loading" && (
        <div className="state-panel" role="status">
          <span className="spinner" aria-hidden="true" />
          <div>
            <h2>Loading system status</h2>
            <p>Checking the protected read-only dashboard signals.</p>
          </div>
        </div>
      )}

      {state === "error" && (
        <div className="state-panel state-panel--error" role="alert">
          <div>
            <h2>System status unavailable</h2>
            <p>The dashboard could not load current service indicators.</p>
          </div>
          <button className="button button--light" type="button" onClick={refresh}>
            Retry
          </button>
        </div>
      )}

      {state === "ready" && summary && (
        <>
          <div className="system-status-summary">
            <div>
              <span className="eyebrow">Current posture</span>
              <strong>{attentionCount === 0 ? "All monitored services healthy" : `${attentionCount} planned or limited areas`}</strong>
            </div>
            <span className="status-badge status-badge--neutral">Read-only</span>
          </div>

          <div className="system-status-grid">
            {items.map((item) => (
              <StatusCard item={item} key={item.name} />
            ))}
          </div>
        </>
      )}
    </section>
  );
}
