import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { fetchProviderConnections, fetchProviderTypes } from "../api/providers";
import type { ProviderConnection, ProviderDescriptor } from "../types/provider";

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "Never";
}

function ProviderChips({ values }: { values: string[] }) {
  if (values.length === 0) return <span className="muted-text">None</span>;
  return (
    <div className="chip-list">
      {values.map((value) => (
        <span className="chip" key={value}>{value}</span>
      ))}
    </div>
  );
}

export function ProviderConnectionsPage() {
  const [descriptors, setDescriptors] = useState<ProviderDescriptor[]>([]);
  const [connections, setConnections] = useState<ProviderConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const [providerTypes, providerConnections] = await Promise.all([
        fetchProviderTypes(signal),
        fetchProviderConnections(signal),
      ]);
      setDescriptors(providerTypes);
      setConnections(providerConnections.items);
      setError("");
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      setError("Provider connection data is currently unavailable.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const descriptorByKey = useMemo(
    () => new Map(descriptors.map((descriptor) => [descriptor.key, descriptor])),
    [descriptors],
  );

  if (loading) {
    return (
      <section className="page">
        <div className="state-panel">
          <span className="spinner" aria-hidden="true" />
          <div>
            <h2>Loading provider connections</h2>
            <p>Reading safe provider metadata for the active company.</p>
          </div>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="page">
        <div className="state-panel state-panel--error">
          <div>
            <h2>Provider connections unavailable</h2>
            <p>{error}</p>
          </div>
          <button className="button" type="button" onClick={() => void load()}>
            Retry
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="page">
      <div className="page-heading page-heading--split">
        <div>
          <span className="eyebrow">Provider foundation</span>
          <h1>Provider Connections</h1>
          <p>Review configured adapters and safe catalog metadata for this company.</p>
        </div>
        <div className="heading-actions">
          <Link className="button button--light" to="/documentation/providers">Learn more</Link>
          <button className="button" type="button" onClick={() => void load()}>
            Refresh
          </button>
        </div>
      </div>

      <div className="metrics-grid">
        <div className="metric-card">
          <p className="metric-card__label">Configured connections</p>
          <strong className="metric-card__value">{connections.length}</strong>
          <p className="metric-card__note">Company-scoped records only</p>
        </div>
        <div className="metric-card">
          <p className="metric-card__label">Active connections</p>
          <strong className="metric-card__value">
            {connections.filter((item) => item.status === "active").length}
          </strong>
          <p className="metric-card__note">Ready for approved dry-run flows</p>
        </div>
        <div className="metric-card">
          <p className="metric-card__label">Provider types</p>
          <strong className="metric-card__value">{descriptors.length}</strong>
          <p className="metric-card__note">Trusted in-process catalog</p>
        </div>
        <div className="metric-card">
          <p className="metric-card__label">Credential exposure</p>
          <strong className="metric-card__value">0</strong>
          <p className="metric-card__note">No credential values are rendered</p>
        </div>
      </div>

      <section className="activity-panel">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Company adapters</span>
            <h2>Configured connections</h2>
          </div>
        </div>
        {connections.length === 0 ? (
          <div className="activity-empty">
            <p>No provider connections exist for this company yet.</p>
          </div>
        ) : (
          <div className="provider-grid">
            {connections.map((connection) => {
              const descriptor = descriptorByKey.get(connection.provider_key);
              return (
                <article className="provider-card" key={connection.id}>
                  <div className="provider-card__header">
                    <div>
                      <h3>{connection.display_name}</h3>
                      <p>{descriptor?.display_name ?? connection.provider_key}</p>
                    </div>
                    <span className="status-badge status-badge--neutral">
                      {connection.status}
                    </span>
                  </div>
                  <dl className="detail-list">
                    <div><dt>Slug</dt><dd>{connection.slug}</dd></div>
                    <div><dt>Authentication</dt><dd>{connection.authentication_type}</dd></div>
                    <div><dt>Updated</dt><dd>{formatDate(connection.updated_at)}</dd></div>
                    <div><dt>Activated</dt><dd>{formatDate(connection.activated_at)}</dd></div>
                  </dl>
                  <div>
                    <span className="detail-label">Capabilities</span>
                    <ProviderChips values={descriptor?.capabilities ?? []} />
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section className="activity-panel">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Trusted catalog</span>
            <h2>Available provider types</h2>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Provider</th>
                <th>Category</th>
                <th>Authentication</th>
                <th>Capabilities</th>
              </tr>
            </thead>
            <tbody>
              {descriptors.map((descriptor) => (
                <tr key={descriptor.key}>
                  <td>
                    <strong>{descriptor.display_name}</strong>
                    <small>{descriptor.key}</small>
                  </td>
                  <td>{descriptor.category}</td>
                  <td>{descriptor.authentication_type}</td>
                  <td><ProviderChips values={descriptor.capabilities} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}
