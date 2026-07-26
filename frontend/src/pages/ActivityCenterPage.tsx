import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchActivity } from "../api/activity";
import { useActiveCompany } from "../context/ActiveCompanyContext";
import type { ActivityEvent, ActivityEventList } from "../types/activity";

const categories = [
  ["", "All activity"],
  ["agent", "Agent"],
  ["approval", "Approvals"],
  ["provider", "Providers"],
  ["email", "Email"],
  ["system", "System"],
] as const;

function formatTime(value: string) {
  return new Date(value).toLocaleString();
}

function categoryIcon(category: string) {
  return ({ agent: "A", approval: "Q", provider: "P", email: "E", system: "S" } as Record<string, string>)[category] ?? "•";
}

function eventHref(event: ActivityEvent) {
  if (event.category === "agent") return "/agent";
  if (event.category === "approval") return "/approvals";
  if (event.category === "provider") return "/providers";
  if (event.category === "email") return "/email";
  return "/audit";
}

function groupByDate(items: ActivityEvent[]) {
  return items.reduce<Record<string, ActivityEvent[]>>((groups, item) => {
    const key = new Date(item.occurred_at).toLocaleDateString();
    groups[key] = groups[key] ?? [];
    groups[key].push(item);
    return groups;
  }, {});
}

function ActivityCard({ event }: { event: ActivityEvent }) {
  const [expanded, setExpanded] = useState(false);
  const details = Object.entries(event.safe_details);
  return (
    <article className={`activity-card activity-card--${event.severity}`}>
      <div className="activity-card__icon" aria-hidden="true">{categoryIcon(event.category)}</div>
      <div className="activity-card__body">
        <div className="activity-card__header">
          <div>
            <h3>{event.title}</h3>
            <p>{event.summary}</p>
          </div>
          <time dateTime={event.occurred_at}>{formatTime(event.occurred_at)}</time>
        </div>
        <div className="activity-card__meta">
          <span className={`status-badge status-badge--${event.severity === "error" ? "danger" : event.severity === "warning" ? "warning" : "neutral"}`}>{event.status}</span>
          <span className="source-badge">{event.source}</span>
          <span className="source-badge">{event.actor_display}</span>
          <a className="text-link" href={eventHref(event)}>Open module</a>
        </div>
        {details.length > 0 && (
          <div className="activity-card__details">
            <button className="link-button" type="button" onClick={() => setExpanded((value) => !value)}>
              {expanded ? "Hide details" : "Show safe details"}
            </button>
            {expanded && (
              <dl>
                {details.map(([key, value]) => (
                  <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{String(value)}</dd></div>
                ))}
              </dl>
            )}
          </div>
        )}
      </div>
    </article>
  );
}

export function ActivityCenterPage() {
  const activeCompany = useActiveCompany();
  const [data, setData] = useState<ActivityEventList | null>(null);
  const [source, setSource] = useState("");
  const [severity, setSeverity] = useState("");
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [requestVersion, setRequestVersion] = useState(0);

  const load = useCallback((signal?: AbortSignal) => {
    setState("loading");
    fetchActivity({ source, severity, limit: 50, offset: 0 }, signal)
      .then((value) => {
        setData(value);
        setState("ready");
      })
      .catch((error) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setData(null);
        setState("error");
      });
  }, [source, severity]);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load, requestVersion]);

  const grouped = useMemo(() => groupByDate(data?.items ?? []), [data]);
  const filtered = Boolean(source || severity);

  return (
    <section className="page activity-center" aria-labelledby="activity-center-title">
      <div className="overview-hero activity-hero">
        <div>
          <span className="eyebrow">Activity Center</span>
          <h1 id="activity-center-title">Everything that happened, in one place.</h1>
          <p>Unified read-only timeline for {activeCompany?.company.name ?? "the active company"}.</p>
        </div>
        <button className="button" type="button" onClick={() => setRequestVersion((value) => value + 1)} disabled={state === "loading"}>
          Refresh
        </button>
      </div>

      <div className="activity-filterbar" aria-label="Activity filters">
        {categories.map(([value, label]) => (
          <button
            key={label}
            className={source === value ? "filter-chip is-active" : "filter-chip"}
            type="button"
            onClick={() => setSource(value)}
          >
            {label}
          </button>
        ))}
        <select aria-label="Severity" value={severity} onChange={(event) => setSeverity(event.target.value)}>
          <option value="">All severities</option>
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="error">Error</option>
        </select>
      </div>

      {state === "loading" && (
        <div className="state-panel" role="status">
          <span className="spinner" aria-hidden="true" />
          <div><h2>Loading activity</h2><p>Building the company timeline.</p></div>
        </div>
      )}
      {state === "error" && (
        <div className="state-panel state-panel--error" role="alert">
          <div><h2>Activity unavailable</h2><p>The activity feed could not be loaded.</p></div>
          <button className="button button--light" type="button" onClick={() => setRequestVersion((value) => value + 1)}>Retry</button>
        </div>
      )}
      {state === "ready" && data && data.items.length === 0 && (
        <div className="empty-panel">
          <span className="empty-panel__icon" aria-hidden="true">A</span>
          <h2>{filtered ? "No matching activity" : "No activity yet"}</h2>
          <p>{filtered ? "Adjust filters to see more company events." : "Agent, approval, provider and email events will appear here."}</p>
        </div>
      )}
      {state === "ready" && data && data.items.length > 0 && (
        <div className="timeline-groups">
          {Object.entries(grouped).map(([date, events]) => (
            <section className="timeline-group" key={date}>
              <h2>{date}</h2>
              <div className="activity-feed">
                {events.map((event) => <ActivityCard event={event} key={event.id} />)}
              </div>
            </section>
          ))}
        </div>
      )}
    </section>
  );
}
