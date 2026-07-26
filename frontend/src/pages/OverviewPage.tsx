import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { fetchActivity } from "../api/activity";
import { fetchDashboardSummary } from "../api/dashboard";
import { useActiveCompany } from "../context/ActiveCompanyContext";
import type { ActivityEvent } from "../types/activity";
import type { DashboardSummary } from "../types/dashboard";

type Tone = "green" | "yellow" | "red";

const quickActions = [
  { to: "/agent", label: "Run Agent", detail: "Use safe read-only tools", icon: "A" },
  { to: "/providers", label: "Providers", detail: "Review connected adapters", icon: "P" },
  { to: "/email", label: "Email Campaigns", detail: "Open campaign visibility", icon: "E" },
  { to: "/approvals", label: "Pending Approvals", detail: "Review queued decisions", icon: "Q" },
] as const;

function healthTone(summary: DashboardSummary, area: string): Tone {
  if (area === "providers" && summary.counts.provider_connections === 0) return "yellow";
  if (area === "email" && summary.counts.provider_connections === 0) return "yellow";
  if (area === "agent" && summary.counts.failed_provider_executions > 0) return "yellow";
  return "green";
}

function statusText(tone: Tone) {
  if (tone === "green") return "Healthy";
  if (tone === "yellow") return "Needs setup";
  return "Attention";
}

function HealthCard({
  title,
  value,
  detail,
  tone,
}: {
  title: string;
  value: string;
  detail: string;
  tone: Tone;
}) {
  return (
    <article className={`ops-card ops-card--${tone}`}>
      <div className="ops-card__topline">
        <span className={`health-dot health-dot--${tone}`} aria-hidden="true" />
        <span>{statusText(tone)}</span>
      </div>
      <strong>{title}</strong>
      <p>{value}</p>
      <small>{detail}</small>
    </article>
  );
}

function SummaryTile({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail: string;
}) {
  return (
    <article className="summary-tile">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

export function OverviewPage() {
  const activeCompany = useActiveCompany();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
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
    Promise.all([
      fetchDashboardSummary(controller.signal),
      fetchActivity({ limit: 4, offset: 0 }, controller.signal),
    ])
      .then(([summaryValue, activityValue]) => {
        setSummary(summaryValue);
        setActivity(activityValue.items);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setSummary(null);
          setActivity([]);
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

  const notifications = useMemo(() => {
    if (!summary) return [];
    const items = [
      summary.counts.pending_approvals > 0
        ? `${summary.counts.pending_approvals} approval request${summary.counts.pending_approvals === 1 ? "" : "s"} awaiting review.`
        : "No pending approvals for this company.",
      summary.counts.provider_connections > 0
        ? `${summary.counts.enabled_provider_connections} provider connection${summary.counts.enabled_provider_connections === 1 ? "" : "s"} active.`
        : "No provider connections configured yet.",
      summary.counts.audit_events > 0
        ? "Recent operational activity is available in the audit trail."
        : "No audit events have been recorded for this company yet.",
    ];
    return items;
  }, [summary]);

  return (
    <section className="page overview-control" aria-labelledby="overview-title">
      <div className="overview-hero">
        <div>
          <span className="eyebrow">Operations center</span>
          <h1 id="overview-title">Command the day with confidence.</h1>
          <p>
            Live, read-only operational signals for{" "}
            <strong>{activeCompany?.company.name ?? "the active company"}</strong>.
          </p>
        </div>
        <button className="button" type="button" onClick={refresh} disabled={loading}>
          Refresh
        </button>
      </div>

      {loading && (
        <div className="state-panel overview-state" role="status">
          <span className="spinner" aria-hidden="true" />
          <div>
            <h2>Loading operations dashboard</h2>
            <p>Gathering health, provider, approval, email and activity signals.</p>
          </div>
        </div>
      )}

      {!loading && error && (
        <div className="state-panel state-panel--error overview-state" role="alert">
          <div>
            <h2>Operations dashboard unavailable</h2>
            <p>{error}</p>
          </div>
          <button className="button button--light" type="button" onClick={refresh}>
            Retry
          </button>
        </div>
      )}

      {!loading && summary && (
        <div className="ops-layout">
          <section className="ops-section ops-section--wide" aria-labelledby="system-health-title">
            <div className="ops-section__heading">
              <div>
                <span className="eyebrow">System health</span>
                <h2 id="system-health-title">All critical services</h2>
              </div>
              <span className="status-badge status-badge--positive">Live</span>
            </div>
            <div className="health-grid">
              <HealthCard title="Backend" value={summary.service.status} detail={summary.service.version} tone="green" />
              <HealthCard title="Database" value={summary.service.readiness} detail="Primary application store" tone="green" />
              <HealthCard title="Agent" value="Read-only runtime" detail={`${summary.counts.provider_executions} executions recorded`} tone={healthTone(summary, "agent")} />
              <HealthCard title="Providers" value={`${summary.counts.enabled_provider_connections}/${summary.counts.provider_connections} active`} detail="Company-scoped adapters" tone={healthTone(summary, "providers")} />
              <HealthCard title="Email" value="Campaign visibility" detail="No live sends enabled" tone={healthTone(summary, "email")} />
              <HealthCard title="Storage" value="Protected" detail="No credential values exposed" tone="green" />
            </div>
          </section>

          <section className="ops-section" aria-labelledby="company-summary-title">
            <div className="ops-section__heading">
              <div>
                <span className="eyebrow">Company summary</span>
                <h2 id="company-summary-title">Active workspace</h2>
              </div>
            </div>
            <div className="summary-grid">
              <SummaryTile label="Company" value={activeCompany?.company.name ?? "Selected"} detail={activeCompany?.membership_role ?? "Platform access"} />
              <SummaryTile label="Providers" value={summary.counts.provider_connections} detail="Configured connections" />
              <SummaryTile label="Approvals" value={summary.counts.pending_approvals} detail="Awaiting decision" />
              <SummaryTile label="Audit Events" value={summary.counts.audit_events} detail="Recorded activity" />
            </div>
          </section>

          <section className="ops-section" aria-labelledby="quick-actions-title">
            <div className="ops-section__heading">
              <div>
                <span className="eyebrow">Quick actions</span>
                <h2 id="quick-actions-title">Jump into work</h2>
              </div>
            </div>
            <div className="quick-action-grid">
              {quickActions.map((item) => (
                <Link className="quick-action" to={item.to} key={item.to}>
                  <span aria-hidden="true">{item.icon}</span>
                  <div>
                    <strong>{item.label}</strong>
                    <small>{item.detail}</small>
                  </div>
                </Link>
              ))}
            </div>
          </section>

          <section className="ops-section ops-section--wide" aria-labelledby="activity-title">
            <div className="ops-section__heading">
              <div>
                <span className="eyebrow">Recent activity</span>
                <h2 id="activity-title">Operational timeline</h2>
              </div>
              <Link className="text-link" to="/activity">View all activity</Link>
            </div>
            {activity.length === 0 ? (
              <div className="activity-empty activity-empty--polished">
                <h3>No activity yet</h3>
                <p>New agent, approval, provider and email events will appear here.</p>
              </div>
            ) : (
              <ul className="ops-timeline">
                {activity.map((event) => (
                  <li key={event.id}>
                    <span className="timeline-marker" aria-hidden="true" />
                    <div>
                      <strong>{event.title}</strong>
                      <span>{event.summary}</span>
                    </div>
                    <time dateTime={event.occurred_at}>
                      {new Date(event.occurred_at).toLocaleString()}
                    </time>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="ops-section" aria-labelledby="notifications-title">
            <div className="ops-section__heading">
              <div>
                <span className="eyebrow">Notifications</span>
                <h2 id="notifications-title">Recent signals</h2>
              </div>
            </div>
            <div className="notification-list">
              {notifications.map((item) => (
                <div className="notification" key={item}>
                  <span className="health-dot health-dot--green" aria-hidden="true" />
                  <p>{item}</p>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
