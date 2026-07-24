import { useCallback, useEffect, useState } from "react";

import { fetchDashboardSummary } from "../api/dashboard";
import { MetricCard } from "../components/MetricCard";
import { StatusBadge } from "../components/StatusBadge";
import type { DashboardSummary } from "../types/dashboard";

const metricLabels = [
  ["provider_connections", "Provider connections", "Configured connections"],
  ["enabled_provider_connections", "Enabled connections", "Ready connections"],
  ["provider_credentials", "Provider credentials", "Stored credential versions"],
  ["pending_approvals", "Pending approvals", "Awaiting review"],
  ["provider_executions", "Provider executions", "Recorded executions"],
  ["failed_provider_executions", "Failed executions", "Needs attention"],
  ["audit_events", "Audit events", "Recorded events"],
] as const;

function formatEventAction(action: string) {
  return action.replaceAll("_", " ").replaceAll(".", " · ");
}

export function OverviewPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [requestVersion, setRequestVersion] = useState(0);

  const refresh = useCallback(() => {
    setRequestVersion((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchDashboardSummary(controller.signal)
      .then(setSummary)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setSummary(null);
          setError(
            reason instanceof Error
              ? reason.message
              : "The dashboard summary is currently unavailable.",
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [requestVersion]);

  return (
    <section className="page" aria-labelledby="overview-title">
      <div className="page-heading page-heading--split">
        <div>
          <span className="eyebrow">Live overview</span>
          <h1 id="overview-title">Operational clarity, at a glance.</h1>
          <p>Read-only signals from the active company and backend service.</p>
        </div>
        <button className="button" type="button" onClick={refresh} disabled={loading}>
          Refresh overview
        </button>
      </div>

      {loading && (
        <div className="state-panel" role="status">
          <span className="spinner" aria-hidden="true" />
          <div>
            <h2>Loading current operations</h2>
            <p>Requesting a safe summary from the backend.</p>
          </div>
        </div>
      )}

      {!loading && error && (
        <div className="state-panel state-panel--error" role="alert">
          <div>
            <h2>Overview unavailable</h2>
            <p>{error}</p>
          </div>
          <button className="button button--light" type="button" onClick={refresh}>
            Retry
          </button>
        </div>
      )}

      {!loading && summary && (
        <>
          <div className="service-strip" aria-label="Service status">
            <div>
              <span className="eyebrow">Backend service</span>
              <strong>CompanyAI API</strong>
            </div>
            <StatusBadge label={summary.service.status} tone="positive" />
            <div>
              <span className="service-strip__label">Database</span>
              <strong>{summary.service.readiness}</strong>
            </div>
            <div>
              <span className="service-strip__label">Environment</span>
              <strong>{summary.service.environment}</strong>
            </div>
            <div>
              <span className="service-strip__label">Version</span>
              <strong>{summary.service.version}</strong>
            </div>
          </div>

          <div className="metrics-grid">
            {metricLabels.map(([key, label, note]) => (
              <MetricCard
                key={key}
                label={label}
                value={summary.counts[key]}
                note={note}
              />
            ))}
          </div>

          <section className="activity-panel" aria-labelledby="activity-title">
            <div className="section-heading">
              <div>
                <span className="eyebrow">Audit trail</span>
                <h2 id="activity-title">Latest activity</h2>
              </div>
              <StatusBadge label="Read only" tone="neutral" />
            </div>
            {summary.recent_audit_events.length === 0 ? (
              <div className="activity-empty">
                <p>No audit events have been recorded for this company yet.</p>
              </div>
            ) : (
              <ul className="activity-list">
                {summary.recent_audit_events.map((event) => (
                  <li key={event.id}>
                    <span className="activity-list__marker" aria-hidden="true" />
                    <div>
                      <strong>{formatEventAction(event.action)}</strong>
                      <span>{event.resource_type.replaceAll("_", " ")}</span>
                    </div>
                    <time dateTime={event.created_at}>
                      {new Date(event.created_at).toLocaleString()}
                    </time>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </section>
  );
}
