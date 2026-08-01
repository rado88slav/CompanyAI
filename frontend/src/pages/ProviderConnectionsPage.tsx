import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  activateProviderConnection,
  createProviderConnection,
  createProviderCredential,
  fetchProviderCredentials,
  fetchProviderConnections,
  fetchProviderTypes,
  rotateProviderCredential,
  testProviderConnectionImap,
  testProviderConnectionSmtp,
  updateProviderConnection,
} from "../api/providers";
import { ApiError } from "../api/client";
import type { ProviderConnection, ProviderDescriptor } from "../types/provider";

type MailboxHealth = {
  smtp?: { status?: string; tested_at?: string; category?: string; message?: string };
  imap?: { status?: string; tested_at?: string; category?: string; message?: string };
  activation_ready?: boolean;
};

function formatDate(value: string | null | undefined): string {
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

function toPort(value: FormDataEntryValue | null, label: string): number {
  const parsed = Number(String(value ?? ""));
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) {
    throw new Error(`${label} must be a valid TCP port.`);
  }
  return parsed;
}

function toHostname(value: string, label: string): string {
  if (!/^[A-Za-z0-9][A-Za-z0-9.-]{0,251}[A-Za-z0-9]$/.test(value) || value.includes("..")) {
    throw new Error(`${label} must be a hostname without protocol or path.`);
  }
  return value;
}

function text(data: FormData, key: string): string {
  return String(data.get(key) ?? "").trim();
}

function mailboxHealth(connection: ProviderConnection): MailboxHealth {
  const value = connection.metadata.generic_smtp_imap_health;
  return value && typeof value === "object" && !Array.isArray(value) ? value as MailboxHealth : {};
}

function configText(connection: ProviderConnection, key: string, fallback = ""): string {
  const value = connection.configuration[key];
  return typeof value === "string" ? value : fallback;
}

function configPort(connection: ProviderConnection, key: string, fallback: number): number {
  const value = connection.configuration[key];
  return typeof value === "number" ? value : fallback;
}

function hasMailboxPassword(connection: ProviderConnection): boolean {
  return connection.credential_status === "configured";
}

function credentialFailureMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "provider_credential_already_configured") {
      return "Password is already configured. Use Replace password to change it.";
    }
    if (error.code === "provider_credential_validation_failed") {
      return "Password could not be stored. Enter the mailbox password and try again.";
    }
    if (error.code === "provider_credential_encryption_unavailable") {
      return "Password could not be stored. Credential encryption is unavailable; run Local Edition health checks and try again.";
    }
    if (error.status === 400 || error.status === 409 || error.status === 422) {
      return "Password could not be stored. Check the password field and try again.";
    }
    return "Password could not be stored. Encryption may be unavailable; run Local Edition health checks and try again.";
  }
  return "Password could not be stored because the API was unreachable. Check Local Edition health and try again.";
}

function HealthLine({ label, item }: { label: string; item: MailboxHealth["smtp"] }) {
  return (
    <div className="mailbox-health-line">
      <strong>{label}</strong>
      <span>{item?.status ?? "not tested"}</span>
      <small>{formatDate(item?.tested_at)} · {item?.message ?? "Test required before activation."}</small>
    </div>
  );
}

export function ProviderConnectionsPage() {
  const [descriptors, setDescriptors] = useState<ProviderDescriptor[]>([]);
  const [connections, setConnections] = useState<ProviderConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showEmailForm, setShowEmailForm] = useState(false);
  const [workingConnectionId, setWorkingConnectionId] = useState("");
  const [formError, setFormError] = useState("");
  const [formMessage, setFormMessage] = useState("");
  const [passwordConnectionId, setPasswordConnectionId] = useState("");
  const [editConnectionId, setEditConnectionId] = useState("");

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
  const hasGenericMailbox = descriptors.some((descriptor) => descriptor.key === "generic_smtp_imap");

  async function submitGenericMailbox(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const password = text(data, "password");
    setWorkingConnectionId("new");
    setFormError("");
    setFormMessage("");
    try {
      if (!password) throw new Error("Mailbox password is required.");
      const connection = await createProviderConnection({
        provider_key: "generic_smtp_imap",
        display_name: text(data, "display_name"),
        slug: text(data, "slug"),
        configuration: {
          email_address: text(data, "email_address"),
          sender_display_name: text(data, "sender_display_name"),
          username: text(data, "username"),
          smtp_host: toHostname(text(data, "smtp_host"), "SMTP host"),
          smtp_port: toPort(data.get("smtp_port"), "SMTP port"),
          smtp_security: text(data, "smtp_security"),
          imap_host: toHostname(text(data, "imap_host"), "IMAP host"),
          imap_port: toPort(data.get("imap_port"), "IMAP port"),
          imap_security: text(data, "imap_security"),
          imap_folder: text(data, "imap_folder"),
          reply_to_address: text(data, "reply_to_address") || undefined,
        },
        metadata: {},
      });
      try {
        await createProviderCredential(connection.id, { secrets: { password } });
      } catch (credentialError) {
        setFormError("Connection saved, but password storage failed. Use Set password on the connection before testing.");
        setConnections((items) => [connection, ...items]);
        return;
      }
      form.reset();
      setConnections((items) => [{ ...connection, credential_status: "configured" }, ...items]);
      setFormMessage("Mailbox saved. Run SMTP and IMAP tests before activation.");
      setShowEmailForm(false);
    } catch (submitError) {
      setFormError(submitError instanceof Error ? submitError.message : "Mailbox connection could not be saved.");
    } finally {
      setWorkingConnectionId("");
    }
  }

  async function runProtocolTest(connection: ProviderConnection, protocol: "smtp" | "imap"): Promise<void> {
    if (!hasMailboxPassword(connection)) {
      setFormError("Password is missing. Set the encrypted mailbox password before testing.");
      return;
    }
    setWorkingConnectionId(`${connection.id}:${protocol}`);
    setFormError("");
    setFormMessage("");
    try {
      const result = protocol === "smtp"
        ? await testProviderConnectionSmtp(connection.id)
        : await testProviderConnectionImap(connection.id);
      setConnections((items) => items.map((item) => item.id === connection.id ? result.connection : item));
      setFormMessage(result.message);
    } catch {
      setFormError(`${protocol.toUpperCase()} test could not be completed. Check mailbox settings and try again.`);
    } finally {
      setWorkingConnectionId("");
    }
  }

  async function submitMailboxPassword(connection: ProviderConnection, event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const password = text(data, "mailbox_password");
    const confirmation = text(data, "mailbox_password_confirmation");
    setWorkingConnectionId(`${connection.id}:password`);
    setFormError("");
    setFormMessage("");
    try {
      if (!password || !confirmation) {
        throw new Error("Enter and confirm the mailbox password.");
      }
      if (password !== confirmation) {
        throw new Error("Password confirmation does not match.");
      }
      if (hasMailboxPassword(connection)) {
        const credentials = await fetchProviderCredentials(connection.id);
        const active = credentials.items.find((item) => item.status === "active");
        if (!active) {
          throw new Error("Active password metadata is unavailable. Refresh and try again.");
        }
        await rotateProviderCredential(connection.id, active.id, { secrets: { password } });
        setFormMessage("Mailbox password replaced. Run SMTP and IMAP tests again before activation.");
      } else {
        try {
          await createProviderCredential(connection.id, { secrets: { password } });
          setFormMessage("Mailbox password configured. Run SMTP and IMAP tests before activation.");
        } catch (createError) {
          if (createError instanceof ApiError && createError.code === "provider_credential_already_configured") {
            setFormMessage("Mailbox password is already configured. Use Replace password to change it.");
          } else {
            throw createError;
          }
        }
      }
      form.reset();
      setPasswordConnectionId("");
      await load();
    } catch (passwordError) {
      form.reset();
      const knownMessage = passwordError instanceof Error && [
        "Enter and confirm the mailbox password.",
        "Password confirmation does not match.",
        "Active password metadata is unavailable. Refresh and try again.",
      ].includes(passwordError.message);
      setFormError(knownMessage && passwordError instanceof Error ? passwordError.message : credentialFailureMessage(passwordError));
    } finally {
      setWorkingConnectionId("");
    }
  }

  async function submitMailboxSettings(connection: ProviderConnection, event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setWorkingConnectionId(`${connection.id}:settings`);
    setFormError("");
    setFormMessage("");
    try {
      const updated = await updateProviderConnection(connection.id, {
        display_name: text(data, "display_name"),
        configuration: {
          email_address: text(data, "email_address"),
          sender_display_name: text(data, "sender_display_name"),
          username: text(data, "username"),
          smtp_host: toHostname(text(data, "smtp_host"), "SMTP host"),
          smtp_port: toPort(data.get("smtp_port"), "SMTP port"),
          smtp_security: text(data, "smtp_security"),
          imap_host: toHostname(text(data, "imap_host"), "IMAP host"),
          imap_port: toPort(data.get("imap_port"), "IMAP port"),
          imap_security: text(data, "imap_security"),
          imap_folder: text(data, "imap_folder"),
          reply_to_address: text(data, "reply_to_address") || undefined,
        },
      });
      setConnections((items) => items.map((item) => item.id === connection.id ? updated : item));
      setEditConnectionId("");
      setFormMessage("Mailbox settings saved. Run SMTP and IMAP tests again before activation.");
    } catch (settingsError) {
      const message = settingsError instanceof Error && (settingsError.message.includes("port must be a valid TCP port.") || settingsError.message.includes("must be a hostname without protocol or path."))
        ? settingsError.message
        : "Mailbox settings could not be saved. Check the non-secret fields and try again.";
      setFormError(message);
    } finally {
      setWorkingConnectionId("");
    }
  }

  async function activateMailbox(connection: ProviderConnection): Promise<void> {
    if (!hasMailboxPassword(connection)) {
      setFormError("Activation requires an active password credential plus successful SMTP and IMAP tests.");
      return;
    }
    setWorkingConnectionId(`${connection.id}:activate`);
    setFormError("");
    setFormMessage("");
    try {
      const updated = await activateProviderConnection(connection.id);
      setConnections((items) => items.map((item) => item.id === connection.id ? updated : item));
      setFormMessage("Mailbox activated.");
    } catch {
      setFormError("Activation requires an active password credential plus successful SMTP and IMAP tests.");
    } finally {
      setWorkingConnectionId("");
    }
  }

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
          <p>Configure safe provider metadata and standards-based mailboxes for this company.</p>
        </div>
        <div className="heading-actions">
          <Link className="button button--light" to="/documentation/providers">Learn more</Link>
          {hasGenericMailbox ? (
            <button className="button" type="button" onClick={() => setShowEmailForm((value) => !value)}>
              {showEmailForm ? "Close mailbox form" : "Add email mailbox"}
            </button>
          ) : null}
          <button className="button button--light" type="button" onClick={() => void load()}>
            Refresh
          </button>
        </div>
      </div>

      {formError ? <div className="state-card error">{formError}</div> : null}
      {formMessage ? <div className="state-card success">{formMessage}</div> : null}

      <section className="acceptance-panel">
        <div>
          <span className="eyebrow">Controlled live acceptance</span>
          <h2>One mailbox, operator-driven tests only</h2>
          <p>Use this flow to validate SMTP authentication/TLS and IMAP read-only folder access before any campaign or worker exists.</p>
        </div>
        <ol>
          <li>Create or select a Generic SMTP/IMAP mailbox.</li>
          <li>Save the password through encrypted credentials only.</li>
          <li>Run Test SMTP and Test IMAP separately.</li>
          <li>Activate only after both protocol checks succeed.</li>
        </ol>
        <div className="acceptance-panel__guardrails">
          <span>No email sent</span>
          <span>No IMAP mutation</span>
          <span>No campaign start</span>
          <span>No password display</span>
        </div>
      </section>

      {showEmailForm ? (
        <form className="mailbox-form" noValidate onSubmit={(event) => void submitGenericMailbox(event)}>
          <div className="section-heading">
            <div>
              <span className="eyebrow">Generic SMTP/IMAP</span>
              <h2>Add mailbox</h2>
            </div>
          </div>
          <div className="mailbox-form__grid">
            <label>Connection name<input name="display_name" required defaultValue="Primary mailbox" /></label>
            <label>Slug<input name="slug" required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" defaultValue="primary-mailbox" /></label>
            <label>Email address<input name="email_address" type="email" required /></label>
            <label>Sender display name<input name="sender_display_name" /></label>
            <label>Username<input name="username" required /></label>
            <label>Password<input name="password" type="password" autoComplete="new-password" required /></label>
            <label>SMTP host<input name="smtp_host" required placeholder="mail.example.com" /></label>
            <label>SMTP port<input name="smtp_port" type="number" min="1" max="65535" required defaultValue="465" /></label>
            <label>SMTP security<select name="smtp_security" defaultValue="ssl_tls"><option value="ssl_tls">SSL/TLS</option><option value="starttls">STARTTLS</option></select></label>
            <label>IMAP host<input name="imap_host" required placeholder="mail.example.com" /></label>
            <label>IMAP port<input name="imap_port" type="number" min="1" max="65535" required defaultValue="993" /></label>
            <label>IMAP security<select name="imap_security" defaultValue="ssl_tls"><option value="ssl_tls">SSL/TLS</option><option value="starttls">STARTTLS</option></select></label>
            <label>IMAP folder<input name="imap_folder" required defaultValue="INBOX" /></label>
            <label>Reply-To address<input name="reply_to_address" type="email" /></label>
          </div>
          <div className="actions">
            <button className="button" type="submit" disabled={workingConnectionId === "new"}>
              Save mailbox
            </button>
            <button className="button button--light" type="button" onClick={() => setShowEmailForm(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : null}

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
          <p className="metric-card__note">Activation is blocked until checks pass</p>
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
              const health = mailboxHealth(connection);
              const isGeneric = connection.provider_key === "generic_smtp_imap";
              const passwordConfigured = hasMailboxPassword(connection);
              const ready = health.activation_ready === true;
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
                  {isGeneric ? (
                    <div className="mailbox-health">
                      <div className="mailbox-credential-status">
                        <span className={`status-badge ${passwordConfigured ? "status-badge--positive" : "status-badge--warning"}`}>
                          {passwordConfigured ? "Password configured" : "Password missing"}
                        </span>
                      </div>
                      <HealthLine label="SMTP" item={health.smtp} />
                      <HealthLine label="IMAP" item={health.imap} />
                      <div className="actions">
                        <button className="button button--light" type="button" onClick={() => setPasswordConnectionId((value) => value === connection.id ? "" : connection.id)}>
                          {passwordConfigured ? "Replace password" : "Set password"}
                        </button>
                        <button className="button button--light" type="button" onClick={() => setEditConnectionId((value) => value === connection.id ? "" : connection.id)}>
                          Edit mailbox settings
                        </button>
                        <button className="button button--light" type="button" disabled={!passwordConfigured || workingConnectionId === `${connection.id}:smtp` || connection.status === "revoked"} onClick={() => void runProtocolTest(connection, "smtp")}>
                          Test SMTP
                        </button>
                        <button className="button button--light" type="button" disabled={!passwordConfigured || workingConnectionId === `${connection.id}:imap` || connection.status === "revoked"} onClick={() => void runProtocolTest(connection, "imap")}>
                          Test IMAP
                        </button>
                        <button className="button" type="button" disabled={!passwordConfigured || !ready || connection.status === "active" || workingConnectionId === `${connection.id}:activate`} onClick={() => void activateMailbox(connection)}>
                          Activate
                        </button>
                      </div>
                      {passwordConnectionId === connection.id ? (
                        <form className="mailbox-form mailbox-form--compact" noValidate onSubmit={(event) => void submitMailboxPassword(connection, event)}>
                          <div className="mailbox-form__grid">
                            <label>Mailbox password<input name="mailbox_password" type="password" autoComplete="new-password" required /></label>
                            <label>Confirm mailbox password<input name="mailbox_password_confirmation" type="password" autoComplete="new-password" required /></label>
                          </div>
                          <div className="actions">
                            <button className="button" type="submit" disabled={workingConnectionId === `${connection.id}:password`}>
                              {passwordConfigured ? "Replace password" : "Set password"}
                            </button>
                            <button className="button button--light" type="button" onClick={() => setPasswordConnectionId("")}>
                              Cancel
                            </button>
                          </div>
                        </form>
                      ) : null}
                      {editConnectionId === connection.id ? (
                        <form className="mailbox-form mailbox-form--compact" noValidate onSubmit={(event) => void submitMailboxSettings(connection, event)}>
                          <div className="mailbox-form__grid">
                            <label>Connection name<input name="display_name" required defaultValue={connection.display_name} /></label>
                            <label>Email address<input name="email_address" type="email" required defaultValue={configText(connection, "email_address")} /></label>
                            <label>Sender display name<input name="sender_display_name" defaultValue={configText(connection, "sender_display_name")} /></label>
                            <label>Username<input name="username" required defaultValue={configText(connection, "username")} /></label>
                            <label>SMTP host<input name="smtp_host" required defaultValue={configText(connection, "smtp_host")} /></label>
                            <label>SMTP port<input name="smtp_port" type="number" min="1" max="65535" required defaultValue={configPort(connection, "smtp_port", 465)} /></label>
                            <label>SMTP security<select name="smtp_security" defaultValue={configText(connection, "smtp_security", "ssl_tls")}><option value="ssl_tls">SSL/TLS</option><option value="starttls">STARTTLS</option></select></label>
                            <label>IMAP host<input name="imap_host" required defaultValue={configText(connection, "imap_host")} /></label>
                            <label>IMAP port<input name="imap_port" type="number" min="1" max="65535" required defaultValue={configPort(connection, "imap_port", 993)} /></label>
                            <label>IMAP security<select name="imap_security" defaultValue={configText(connection, "imap_security", "ssl_tls")}><option value="ssl_tls">SSL/TLS</option><option value="starttls">STARTTLS</option></select></label>
                            <label>IMAP folder<input name="imap_folder" required defaultValue={configText(connection, "imap_folder", "INBOX")} /></label>
                            <label>Reply-To address<input name="reply_to_address" type="email" defaultValue={configText(connection, "reply_to_address")} /></label>
                          </div>
                          <div className="actions">
                            <button className="button" type="submit" disabled={workingConnectionId === `${connection.id}:settings`}>
                              Save settings
                            </button>
                            <button className="button button--light" type="button" onClick={() => setEditConnectionId("")}>
                              Cancel
                            </button>
                          </div>
                        </form>
                      ) : null}
                    </div>
                  ) : null}
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
