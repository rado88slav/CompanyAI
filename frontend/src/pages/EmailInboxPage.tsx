import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { emailApi } from "../api/email";
import { EMAIL_EMERGENCY_STOP_DISABLE_CONFIRMATION, type CampaignSchedulePreview, type CampaignScheduleSettings, type EmailCampaign, type EmailSandboxStatus, type InboundEmail, type SingleMessageApproval, type SingleMessagePreview, type SingleMessageRecipientAllowlist, type SingleMessageTestPayload, type WorkerSimulation } from "../types/email";

const weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function asTime(value: string) {
  return value.slice(0, 5);
}

export function EmailInboxPage() {
  const [items, setItems] = useState<InboundEmail[]>([]);
  const [campaigns, setCampaigns] = useState<EmailCampaign[]>([]);
  const [schedule, setSchedule] = useState<CampaignScheduleSettings | null>(null);
  const [preview, setPreview] = useState<CampaignSchedulePreview | null>(null);
  const [workerSimulation, setWorkerSimulation] = useState<WorkerSimulation | null>(null);
  const [singlePreview, setSinglePreview] = useState<SingleMessagePreview | null>(null);
  const [singleApproval, setSingleApproval] = useState<SingleMessageApproval | null>(null);
  const [singleApprovalStatus, setSingleApprovalStatus] = useState("");
  const [singleActionBusy, setSingleActionBusy] = useState("");
  const [singleError, setSingleError] = useState("");
  const [singleFailureChecks, setSingleFailureChecks] = useState<Record<string, boolean>>({});
  const [singleMode, setSingleMode] = useState<"simulation" | "live_test">("simulation");
  const [liveConfirmation, setLiveConfirmation] = useState("");
  const [allowlist, setAllowlist] = useState<SingleMessageRecipientAllowlist | null>(null);
  const [allowlistEmail, setAllowlistEmail] = useState("");
  const [allowlistBusy, setAllowlistBusy] = useState(false);
  const [allowlistError, setAllowlistError] = useState("");
  const [sandbox, setSandbox] = useState<EmailSandboxStatus | null>(null);
  const [senderEmail, setSenderEmail] = useState("");
  const [senderMailboxId, setSenderMailboxId] = useState("");
  const [senderBusy, setSenderBusy] = useState(false);
  const [senderError, setSenderError] = useState("");
  const [emergencyBusy, setEmergencyBusy] = useState(false);
  const [emergencyError, setEmergencyError] = useState("");
  const [emergencyConfirmation, setEmergencyConfirmation] = useState("");
  const [singleForm, setSingleForm] = useState<SingleMessageTestPayload>({
    provider_connection_id: "",
    recipient_email: "",
    subject: "[COMPANYAI TEST] Controlled mailbox test",
    body: "This is a controlled CompanyAI single-message test preview.",
    idempotency_key: `single-test-${Date.now()}`,
  });
  const [mailboxes, setMailboxes] = useState<Array<{id: string; provider_key: string; display_name: string; status: string}>>([]);
  const [message, setMessage] = useState("");
  const [state, setState] = useState<"loading"|"ready"|"error">("loading");
  const currentPreviewKey = useMemo(() => JSON.stringify({...singleForm, mode: singleMode}), [singleForm, singleMode]);
  const previewKey = singlePreview ? JSON.stringify({
    provider_connection_id: singlePreview.provider_connection_id,
    recipient_email: singlePreview.recipient_email,
    subject: singlePreview.subject,
    body: singlePreview.body,
    idempotency_key: singlePreview.idempotency_key,
    mode: singlePreview.mode,
  }) : "";
  const previewIsCurrent = Boolean(singlePreview && previewKey === currentPreviewKey);
  const approvalIsApproved = singleApprovalStatus === "approved";
  const load = useCallback(() => {
    setState("loading");
    Promise.all([emailApi.list(), emailApi.campaigns(), emailApi.schedule(), emailApi.connections(), emailApi.emailSandbox()])
      .then(([emailValue, campaignValue, scheduleValue, connectionValue, sandboxValue]) => {
        setItems(emailValue.items);
        setCampaigns(campaignValue.items);
        setSchedule(scheduleValue);
        setSandbox(sandboxValue);
        setAllowlist({recipient_allowlist: sandboxValue.recipient_allowlist, exact_only: sandboxValue.exact_only});
        setMailboxes(connectionValue.items.filter((item) => item.provider_key === "generic_smtp_imap"));
        setSingleForm((current) => ({...current, provider_connection_id: current.provider_connection_id || connectionValue.items.find((item) => item.provider_key === "generic_smtp_imap" && item.status === "active")?.id || ""}));
        setState("ready");
      })
      .catch(() => setState("error"));
  }, []);
  useEffect(load, [load]);
  function invalidateSingleMessageState() {
    setSinglePreview(null);
    setSingleApproval(null);
    setSingleApprovalStatus("");
    setLiveConfirmation("");
    setSingleError("");
    setSingleFailureChecks({});
  }
  function updateSingleForm(mutator: (current: SingleMessageTestPayload) => SingleMessageTestPayload) {
    invalidateSingleMessageState();
    setSingleForm(mutator);
  }
  function changeSingleMode(mode: "simulation" | "live_test") {
    invalidateSingleMessageState();
    setSingleMode(mode);
  }
  function applySandboxStatus(value: EmailSandboxStatus) {
    setSandbox(value);
    setAllowlist({recipient_allowlist: value.recipient_allowlist, exact_only: value.exact_only});
    invalidateSingleMessageState();
  }
  function updateSchedule(mutator: (current: CampaignScheduleSettings) => CampaignScheduleSettings) {
    setSchedule((current) => current ? mutator(current) : current);
  }
  async function saveSchedule() {
    if (!schedule) return;
    setMessage("");
    const saved = await emailApi.saveSchedule(schedule);
    setSchedule(saved);
    setMessage("Schedule settings saved.");
  }
  async function previewSchedule() {
    setMessage("");
    const value = await emailApi.previewSchedule(12);
    setPreview(value);
    setMessage("Dry-run preview refreshed.");
  }
  async function simulateWorker() {
    setMessage("");
    const value = await emailApi.simulateWorker();
    setWorkerSimulation(value);
    setMessage("Worker simulation recorded.");
  }
  async function previewSingleMessage() {
    setMessage("");
    setSingleError("");
    setSingleActionBusy("preview");
    try {
      const value = await emailApi.previewSingleMessage({...singleForm, mode: singleMode});
      setSinglePreview(value);
      setSingleApproval(null);
      setSingleApprovalStatus("");
      setSingleFailureChecks({});
      setMessage("Single-message preview ready.");
    } catch (error) {
      setSingleError(error instanceof ApiError ? error.message : "Single-message preview could not be completed.");
      setSingleFailureChecks(error instanceof ApiError && error.policyChecks ? error.policyChecks : {});
    } finally {
      setSingleActionBusy("");
    }
  }
  async function requestSingleApproval() {
    if (!singlePreview || !previewIsCurrent) return;
    setMessage("");
    setSingleError("");
    setSingleActionBusy("approval");
    try {
      const value = await emailApi.requestSingleMessageApproval({...singleForm, mode: singleMode}, singlePreview.payload_digest);
      setSinglePreview(value);
      setSingleApproval(value);
      setSingleApprovalStatus("pending");
      setMessage(singleMode === "live_test" ? "Approval request created for one LIVE TEST email." : "Approval request created for one simulated test email.");
    } catch (error) {
      setSingleError(error instanceof ApiError ? error.message : "Approval request could not be created.");
    } finally {
      setSingleActionBusy("");
    }
  }
  async function refreshSingleApprovalStatus() {
    if (!singleApproval) return;
    setSingleError("");
    setSingleActionBusy("approval-status");
    try {
      const approvals = await emailApi.singleMessageApprovals();
      const current = approvals.items.find((item) => item.id === singleApproval.approval_request_id);
      if (!current) {
        setSingleApprovalStatus("not found");
        setSingleError("Approval request is not available for this company.");
      } else {
        setSingleApprovalStatus(current.status);
        setMessage(`Approval status: ${current.status}.`);
      }
    } catch (error) {
      setSingleError(error instanceof ApiError ? error.message : "Approval status could not be refreshed.");
    } finally {
      setSingleActionBusy("");
    }
  }
  async function executeSingleSimulation() {
    if (!singleApproval || !approvalIsApproved || !previewIsCurrent) return;
    setMessage("");
    setSingleActionBusy("simulation");
    try {
      const value = await emailApi.executeSingleMessageSimulation(singleApproval.provider_execution_id);
      setMessage(`Simulation ${value.status}; external action: ${value.external_action_taken ? "yes" : "no"}.`);
    } catch (error) {
      setSingleError(error instanceof ApiError ? error.message : "Simulation could not be executed.");
    } finally {
      setSingleActionBusy("");
    }
  }
  async function executeSingleLive() {
    if (!singleApproval || !approvalIsApproved || !previewIsCurrent || liveConfirmation !== "SEND ONE TEST EMAIL") return;
    setMessage("");
    setSingleActionBusy("live");
    try {
      const value = await emailApi.executeSingleMessageLive(singleApproval.provider_execution_id, singleForm.subject, singleForm.body);
      setMessage(`LIVE TEST ${value.status}; SMTP accepted: ${value.status === "succeeded" ? "yes" : "no"}; delivery claimed: no.`);
      setLiveConfirmation("");
    } catch (error) {
      setSingleError(error instanceof ApiError ? error.message : "LIVE TEST could not be executed.");
    } finally {
      setSingleActionBusy("");
    }
  }
  async function addAllowlistRecipient() {
    if (!allowlistEmail || allowlistBusy) return;
    setMessage("");
    setAllowlistError("");
    setAllowlistBusy(true);
    try {
      const value = await emailApi.addSingleMessageRecipientAllowlist(allowlistEmail);
      setAllowlist(value);
      setAllowlistEmail("");
      const sandboxValue = await emailApi.emailSandbox();
      applySandboxStatus(sandboxValue);
      setMessage("Exact test recipient allowlist updated.");
    } catch (error) {
      setAllowlistError(error instanceof ApiError ? error.message : "The exact recipient allowlist could not be updated.");
    } finally {
      setAllowlistBusy(false);
    }
  }
  async function removeAllowlistRecipient(recipientEmail: string) {
    if (allowlistBusy) return;
    setMessage("");
    setAllowlistError("");
    setAllowlistBusy(true);
    try {
      const value = await emailApi.removeSingleMessageRecipientAllowlist(recipientEmail);
      setAllowlist(value);
      const sandboxValue = await emailApi.emailSandbox();
      applySandboxStatus(sandboxValue);
      setMessage("Exact test recipient allowlist updated.");
    } catch (error) {
      setAllowlistError(error instanceof ApiError ? error.message : "The exact recipient allowlist could not be updated.");
    } finally {
      setAllowlistBusy(false);
    }
  }
  async function addSandboxSenderFromEmail() {
    if (!senderEmail || senderBusy) return;
    setSenderBusy(true);
    setSenderError("");
    setMessage("");
    try {
      const value = await emailApi.addEmailSandboxSender(senderEmail);
      applySandboxStatus(value);
      setSenderEmail("");
      setMessage("Exact test sender allowlist updated.");
    } catch (error) {
      setSenderError(error instanceof ApiError ? error.message : "The exact sender allowlist could not be updated.");
    } finally {
      setSenderBusy(false);
    }
  }
  async function addSandboxSenderFromMailbox() {
    if (!senderMailboxId || senderBusy) return;
    setSenderBusy(true);
    setSenderError("");
    setMessage("");
    try {
      const value = await emailApi.addEmailSandboxMailboxSender(senderMailboxId);
      applySandboxStatus(value);
      setSenderMailboxId("");
      setMessage("Exact test sender allowlist updated.");
    } catch (error) {
      setSenderError(error instanceof ApiError ? error.message : "The selected mailbox sender could not be allowlisted.");
    } finally {
      setSenderBusy(false);
    }
  }
  async function removeSandboxSender(sender: string) {
    if (senderBusy) return;
    setSenderBusy(true);
    setSenderError("");
    setMessage("");
    try {
      const value = await emailApi.removeEmailSandboxSender(sender);
      applySandboxStatus(value);
      setMessage("Exact test sender allowlist updated.");
    } catch (error) {
      setSenderError(error instanceof ApiError ? error.message : "The exact sender allowlist could not be updated.");
    } finally {
      setSenderBusy(false);
    }
  }
  async function setEmergencyStop(value: boolean) {
    if (emergencyBusy) return;
    setEmergencyBusy(true);
    setEmergencyError("");
    setMessage("");
    try {
      const status = await emailApi.setEmailSandboxEmergencyStop(value, value ? undefined : emergencyConfirmation);
      applySandboxStatus(status);
      setEmergencyConfirmation("");
      setMessage(value ? "Email Sandbox emergency stop is active." : "Email Sandbox emergency stop is inactive for controlled tests.");
    } catch (error) {
      setEmergencyError(error instanceof ApiError ? error.message : "Emergency stop could not be updated.");
    } finally {
      setEmergencyBusy(false);
    }
  }
  async function pauseSchedule() {
    const value = await emailApi.pauseSchedule();
    setSchedule(value);
    setMessage("Automation paused.");
  }
  async function resumeSchedule() {
    const value = await emailApi.resumeSchedule();
    setSchedule(value);
    setMessage("Automation resumed.");
  }
  return <section className="module-page">
    <div className="page-heading page-heading--split"><div><p className="eyebrow">Email</p><h1>Email Operations</h1><p>Company-scoped inbox, read-only campaigns and restricted sandbox testing.</p></div><div className="heading-actions"><Link className="button button--light" to="/documentation/email-sandbox">Email Sandbox Guide</Link><button onClick={load} disabled={state === "loading"}>Refresh</button></div></div>
    <section className="sandbox-panel">
      <div>
        <p className="eyebrow">Restricted test mode</p>
        <h2>Email Sandbox</h2>
        <p>Outbound email is backend-gated by exact allowlists, approval, duplicate-send protection, quotas and a global emergency stop.</p>
      </div>
      <div className="sandbox-grid" aria-label="Email sandbox safeguards">
        <span><strong>Recipients</strong> {sandbox?.recipient_allowlist.length ?? 0} exact</span>
        <span><strong>Senders</strong> {sandbox?.sender_allowlist.length ?? 0} exact</span>
        <span><strong>Per message</strong> {sandbox?.max_recipients_per_message ?? 1} recipient</span>
        <span><strong>Hourly</strong> {sandbox?.max_messages_per_hour ?? 5} messages</span>
        <span><strong>Daily</strong> {sandbox?.max_messages_per_day ?? 10} messages</span>
        <span><strong>Approval</strong> {sandbox?.approval_required === false ? "Not required" : "Required"}</span>
        <span><strong>Follow-ups</strong> {sandbox?.followups_enabled ? "Enabled" : "Disabled"}</span>
        <span><strong>Attachments</strong> {sandbox?.attachments_enabled ? "Enabled" : "Disabled"}</span>
      </div>
      <div className="sandbox-stop" aria-label="Emergency stop status">
        <strong>Emergency stop</strong>
        <span className={sandbox?.emergency_stop ? "is-active" : "is-inactive"}>{sandbox?.emergency_stop ? "ACTIVE" : "INACTIVE"}</span>
        <button type="button" onClick={() => void setEmergencyStop(true)} disabled={emergencyBusy || sandbox?.emergency_stop === true}>Enable stop</button>
        <label>Disable confirmation
          <input value={emergencyConfirmation} onChange={(event) => setEmergencyConfirmation(event.target.value)} placeholder={EMAIL_EMERGENCY_STOP_DISABLE_CONFIRMATION} />
        </label>
        <button type="button" className="danger" onClick={() => void setEmergencyStop(false)} disabled={emergencyBusy || sandbox?.emergency_stop === false || emergencyConfirmation !== EMAIL_EMERGENCY_STOP_DISABLE_CONFIRMATION}>{emergencyBusy ? "Updating" : "Disable stop"}</button>
        <small>Disabling allows approved LIVE TEST email to reach an external SMTP provider.</small>
        {emergencyError && <p role="alert" className="error-text">{emergencyError}</p>}
      </div>
    </section>
    {state === "loading" && <div className="state-card">Loading inbound email…</div>}
    {state === "error" && <div className="state-card error"><h2>Inbox unavailable</h2><button onClick={load}>Retry</button></div>}
    {state === "ready" && schedule && <section className="automation-panel">
      <div className="section-heading"><div><p className="eyebrow">Campaign scheduler</p><h2>Email Automation</h2></div><span className="status-pill">{schedule.status}</span></div>
      <div className="automation-grid">
        <label>Timezone
          <input value={schedule.timezone} onChange={(event) => updateSchedule((current) => ({...current, timezone: event.target.value}))} />
        </label>
        <label>Approval mode
          <select value={schedule.approval_mode} onChange={(event) => updateSchedule((current) => ({...current, approval_mode: event.target.value as CampaignScheduleSettings["approval_mode"]}))}>
            <option value="draft_only">Draft only</option>
            <option value="campaign">Campaign</option>
            <option value="batch">Batch</option>
            <option value="period">Period</option>
            <option value="mailboxes">Mailboxes</option>
            <option value="per_action">Per action</option>
          </select>
        </label>
        <label>Start date
          <input type="date" value={schedule.start_date || ""} onChange={(event) => updateSchedule((current) => ({...current, start_date: event.target.value || null}))} />
        </label>
        <label>End date
          <input type="date" value={schedule.end_date || ""} onChange={(event) => updateSchedule((current) => ({...current, end_date: event.target.value || null}))} />
        </label>
      </div>
      <div className="weekday-row" aria-label="Allowed weekdays">
        {weekdays.map((label, index) => <label key={label}><input type="checkbox" checked={schedule.allowed_weekdays.includes(index)} onChange={(event) => updateSchedule((current) => ({...current, allowed_weekdays: event.target.checked ? [...current.allowed_weekdays, index].sort() : current.allowed_weekdays.filter((item) => item !== index)}))} />{label}</label>)}
      </div>
      <div className="automation-grid">
        {schedule.send_windows.map((window, index) => <div className="window-row" key={`${window.start}-${index}`}>
          <label>Window start
            <input type="time" value={asTime(window.start)} onChange={(event) => updateSchedule((current) => ({...current, send_windows: current.send_windows.map((item, itemIndex) => itemIndex === index ? {...item, start: event.target.value} : item)}))} />
          </label>
          <label>Window end
            <input type="time" value={asTime(window.end)} onChange={(event) => updateSchedule((current) => ({...current, send_windows: current.send_windows.map((item, itemIndex) => itemIndex === index ? {...item, end: event.target.value} : item)}))} />
          </label>
          <button type="button" onClick={() => updateSchedule((current) => ({...current, send_windows: current.send_windows.filter((_, itemIndex) => itemIndex !== index)}))}>Remove</button>
        </div>)}
        <button type="button" onClick={() => updateSchedule((current) => ({...current, send_windows: [...current.send_windows, {start: "09:00", end: "11:00"}]}))}>Add window</button>
      </div>
      <div className="automation-grid">
        <label>Minimum delay
          <input type="number" min="1" value={schedule.randomized_timing.minimum_delay_minutes} onChange={(event) => updateSchedule((current) => ({...current, randomized_timing: {...current.randomized_timing, minimum_delay_minutes: Number(event.target.value)}}))} />
        </label>
        <label>Maximum delay
          <input type="number" min="1" value={schedule.randomized_timing.maximum_delay_minutes} onChange={(event) => updateSchedule((current) => ({...current, randomized_timing: {...current.randomized_timing, maximum_delay_minutes: Number(event.target.value)}}))} />
        </label>
        <label>Jitter
          <input type="number" min="0" value={schedule.randomized_timing.jitter_minutes} onChange={(event) => updateSchedule((current) => ({...current, randomized_timing: {...current.randomized_timing, jitter_minutes: Number(event.target.value)}}))} />
        </label>
        <label>Daily campaign limit
          <input type="number" min="1" value={schedule.limits.campaign_daily} onChange={(event) => updateSchedule((current) => ({...current, limits: {...current.limits, campaign_daily: Number(event.target.value)}}))} />
        </label>
        <label>Mailbox daily limit
          <input type="number" min="1" value={schedule.limits.mailbox_daily} onChange={(event) => updateSchedule((current) => ({...current, limits: {...current.limits, mailbox_daily: Number(event.target.value)}}))} />
        </label>
        <label>Mailbox rotation
          <select value={schedule.mailbox_rotation.strategy} onChange={(event) => updateSchedule((current) => ({...current, mailbox_rotation: {...current.mailbox_rotation, strategy: event.target.value as CampaignScheduleSettings["mailbox_rotation"]["strategy"]}}))}>
            <option value="round_robin">Round robin</option>
            <option value="random">Random</option>
            <option value="preferred_with_fallback">Preferred fallback</option>
          </select>
        </label>
      </div>
      <div className="mailbox-picker">
        <div><strong>Mailboxes</strong><span>{mailboxes.filter((item) => item.status === "active").length}/{mailboxes.length} active Generic SMTP/IMAP</span></div>
        {mailboxes.length === 0 ? <p>No Generic SMTP/IMAP mailboxes configured.</p> : mailboxes.map((mailbox) => <label key={mailbox.id}><input type="checkbox" checked={schedule.mailbox_rotation.allowed_connection_ids.includes(mailbox.id)} onChange={(event) => updateSchedule((current) => ({...current, mailbox_rotation: {...current.mailbox_rotation, allowed_connection_ids: event.target.checked ? [...current.mailbox_rotation.allowed_connection_ids, mailbox.id] : current.mailbox_rotation.allowed_connection_ids.filter((item) => item !== mailbox.id)}}))} />{mailbox.display_name}<span>{mailbox.status}</span></label>)}
      </div>
      <div className="automation-grid">
        <label>Maximum follow-ups
          <input type="number" min="0" max="10" value={schedule.maximum_follow_ups} onChange={(event) => updateSchedule((current) => ({...current, maximum_follow_ups: Number(event.target.value)}))} />
        </label>
        <label>Bounce pause %
          <input type="number" min="0" max="100" value={schedule.auto_pause.bounce_rate_percent} onChange={(event) => updateSchedule((current) => ({...current, auto_pause: {...current.auto_pause, bounce_rate_percent: Number(event.target.value)}}))} />
        </label>
        <label><input type="checkbox" checked={schedule.auto_pause.approval_unavailable} onChange={(event) => updateSchedule((current) => ({...current, auto_pause: {...current.auto_pause, approval_unavailable: event.target.checked}}))} />Approval unavailable</label>
        <label><input type="checkbox" checked={schedule.mailbox_rotation.reply_monitoring_required} onChange={(event) => updateSchedule((current) => ({...current, mailbox_rotation: {...current.mailbox_rotation, reply_monitoring_required: event.target.checked}}))} />Reply monitoring</label>
      </div>
      <div className="automation-actions">
        <button type="button" onClick={saveSchedule}>Save settings</button>
        <button type="button" onClick={previewSchedule}>Preview dry run</button>
        <button type="button" onClick={simulateWorker}>Simulate worker</button>
        <button type="button" onClick={pauseSchedule}>Pause</button>
        <button type="button" onClick={resumeSchedule}>Resume</button>
        {message && <span>{message}</span>}
      </div>
      {preview && <div className="table-wrap"><table><thead><tr><th>#</th><th>Planned local</th><th>Mailbox</th><th>Step</th><th>Status</th></tr></thead><tbody>{preview.slots.slice(0, 12).map((slot) => <tr key={`${slot.sequence}-${slot.recipient_step}`}><td>{slot.sequence}</td><td>{slot.planned_at_local ? new Date(slot.planned_at_local).toLocaleString() : "-"}</td><td>{slot.mailbox_display_name || "None"}</td><td>{slot.recipient_step}</td><td>{slot.status}</td></tr>)}{preview.skipped.map((slot) => <tr key={`skipped-${slot.reason}`}><td>-</td><td>-</td><td>None</td><td>{slot.recipient_step}</td><td>{slot.reason || slot.status}</td></tr>)}</tbody></table></div>}
      {workerSimulation && <div className="state-card"><h3>Worker simulation only</h3><p>Would execute {workerSimulation.would_execute.length} actions. Provider execution created: {workerSimulation.provider_execution_created ? "yes" : "no"}. External action: {workerSimulation.external_action_taken ? "yes" : "no"}.</p></div>}
    </section>}
    {state === "ready" && <section className="single-message-panel">
      <div className="section-heading">
        <div><p className="eyebrow">Controlled single-message test</p><h2>One Test Email</h2></div>
        <span className="status-pill">{singleMode === "live_test" ? "LIVE TEST external action" : "simulation only"}</span>
      </div>
      <div className="segmented-control" role="group" aria-label="Single-message mode">
        <button type="button" className={singleMode === "simulation" ? "is-active" : ""} onClick={() => changeSingleMode("simulation")}>Simulation</button>
        <button type="button" className={singleMode === "live_test" ? "is-active" : ""} onClick={() => changeSingleMode("live_test")}>LIVE TEST</button>
      </div>
      <div className="sandbox-grid" aria-label="Single-message safeguards">
        <span><strong>Recipient</strong> exactly one</span>
        <span><strong>Subject</strong> [COMPANYAI TEST]</span>
        <span><strong>Approval</strong> required</span>
        <span><strong>Live send</strong> {singleMode === "live_test" ? "manual only" : "disabled"}</span>
      </div>
      {singleMode === "live_test" && <div className="state-card warning">
        <h3>LIVE TEST external action</h3>
        <p>This mode can send exactly one plain-text SMTP message after approval and final typed confirmation. SMTP accepted does not mean delivered.</p>
      </div>}
      <div className="automation-grid">
        <label>Exact sender allowlist
          <input value={senderEmail} onChange={(event) => setSenderEmail(event.target.value)} placeholder="sender@example.com" />
        </label>
        <button type="button" onClick={addSandboxSenderFromEmail} disabled={!senderEmail || senderBusy}>{senderBusy ? "Updating" : "Add exact sender"}</button>
        <label>Allow active mailbox sender
          <select value={senderMailboxId} onChange={(event) => setSenderMailboxId(event.target.value)}>
            <option value="">Select active mailbox</option>
            {mailboxes.filter((mailbox) => mailbox.status === "active").map((mailbox) => <option key={mailbox.id} value={mailbox.id}>{mailbox.display_name}</option>)}
          </select>
        </label>
        <button type="button" onClick={addSandboxSenderFromMailbox} disabled={!senderMailboxId || senderBusy}>{senderBusy ? "Updating" : "Allow mailbox sender"}</button>
        <div className="state-card">
          <strong>Allowed test senders</strong>
          {sandbox?.sender_allowlist.length ? <ul className="compact-list">{sandbox.sender_allowlist.map((sender) => <li key={sender}><span>{sender}</span><button type="button" onClick={() => void removeSandboxSender(sender)} disabled={senderBusy}>Remove</button></li>)}</ul> : <p>No exact senders configured.</p>}
          {senderError && <p role="alert" className="error-text">{senderError}</p>}
        </div>
        <label>Exact recipient allowlist
          <input value={allowlistEmail} onChange={(event) => setAllowlistEmail(event.target.value)} placeholder="person@example.com" />
        </label>
        <button type="button" onClick={addAllowlistRecipient} disabled={!allowlistEmail || allowlistBusy}>{allowlistBusy ? "Updating" : "Add exact recipient"}</button>
        <div className="state-card">
          <strong>Allowed test recipients</strong>
          {allowlist?.recipient_allowlist.length ? <ul className="compact-list">{allowlist.recipient_allowlist.map((recipient) => <li key={recipient}><span>{recipient}</span><button type="button" onClick={() => removeAllowlistRecipient(recipient)} disabled={allowlistBusy}>Remove</button></li>)}</ul> : <p>No exact recipients configured.</p>}
          {allowlistError && <p className="error-text">{allowlistError}</p>}
        </div>
      </div>
      <div className="automation-grid">
        <label>Mailbox
          <select value={singleForm.provider_connection_id} onChange={(event) => updateSingleForm((current) => ({...current, provider_connection_id: event.target.value}))}>
            <option value="">Select active mailbox</option>
            {mailboxes.map((mailbox) => <option key={mailbox.id} value={mailbox.id}>{mailbox.display_name} ({mailbox.status})</option>)}
          </select>
        </label>
        <label>Recipient
          <input value={singleForm.recipient_email} onChange={(event) => updateSingleForm((current) => ({...current, recipient_email: event.target.value}))} />
        </label>
        <label>Idempotency key
          <input value={singleForm.idempotency_key} onChange={(event) => updateSingleForm((current) => ({...current, idempotency_key: event.target.value}))} />
        </label>
      </div>
      <label>Subject
        <input value={singleForm.subject} onChange={(event) => updateSingleForm((current) => ({...current, subject: event.target.value}))} />
      </label>
      <label>Body
        <textarea value={singleForm.body} onChange={(event) => updateSingleForm((current) => ({...current, body: event.target.value}))} />
      </label>
      {singleError && <p role="alert" className="error-text">{singleError}</p>}
      {!singleForm.provider_connection_id && <p className="settings-note">Select an active tested mailbox before preview.</p>}
      {!singleForm.recipient_email && <p className="settings-note">Enter exactly one allowlisted recipient before preview.</p>}
      {sandbox && sandbox.sender_allowlist.length === 0 && <p className="settings-note">Add the active mailbox sender to the exact sender allowlist before preview.</p>}
      {singleMode === "live_test" && sandbox?.emergency_stop && <p className="warning-text">Emergency stop is ACTIVE. LIVE TEST preview and execution remain blocked until an authorized administrator disables it explicitly.</p>}
      {Object.keys(singleFailureChecks).length > 0 && <div className="sandbox-grid" aria-label="Blocked preview policy checks">
        {Object.entries(singleFailureChecks).map(([key, value]) => <span key={key}><strong>{key.replaceAll("_", " ")}</strong> {value ? "OK" : "Blocked"}</span>)}
      </div>}
      {singlePreview && !previewIsCurrent && <p className="warning-text">Message fields changed. Preview again before requesting approval.</p>}
      {singleApproval && singleApprovalStatus !== "approved" && <p className="settings-note">Approval status is {singleApprovalStatus || "pending"}. Execution remains disabled until approval is complete.</p>}
      <div className="automation-actions">
        <button type="button" onClick={previewSingleMessage} disabled={!singleForm.provider_connection_id || !singleForm.recipient_email || singleActionBusy === "preview"}>{singleActionBusy === "preview" ? "Previewing" : "Preview one message"}</button>
        <button type="button" onClick={requestSingleApproval} disabled={!singlePreview || !previewIsCurrent || Boolean(singleApproval) || singleActionBusy === "approval"}>{singleActionBusy === "approval" ? "Requesting" : "Request approval"}</button>
        <button type="button" onClick={refreshSingleApprovalStatus} disabled={!singleApproval || singleActionBusy === "approval-status"}>{singleActionBusy === "approval-status" ? "Refreshing" : "Refresh approval status"}</button>
        <button type="button" onClick={executeSingleSimulation} disabled={!singleApproval || !approvalIsApproved || !previewIsCurrent || singleActionBusy === "simulation"}>Execute simulation</button>
        <button type="button" onClick={executeSingleLive} disabled={!singleApproval || !approvalIsApproved || !previewIsCurrent || singleApproval.mode !== "live_test" || liveConfirmation !== "SEND ONE TEST EMAIL" || singleActionBusy === "live"}>Execute LIVE TEST</button>
      </div>
      {singleApproval?.mode === "live_test" && approvalIsApproved && <label>Final live confirmation
        <input value={liveConfirmation} onChange={(event) => setLiveConfirmation(event.target.value)} placeholder="SEND ONE TEST EMAIL" />
      </label>}
      {singlePreview && <div className="state-card">
        <h3>Preview before approval</h3>
        <p><strong>Status:</strong> Successful preview · {singlePreview.mode === "live_test" ? "LIVE TEST" : "Simulation"}</p>
        <p><strong>From:</strong> {singlePreview.sender_email}</p>
        <p><strong>To:</strong> {singlePreview.recipient_email}</p>
        <p><strong>Subject:</strong> {singlePreview.subject}</p>
        <p>{singlePreview.body}</p>
        <small>Digest {singlePreview.payload_digest.slice(0, 12)}… · Idempotency {singlePreview.idempotency_key}. Live send available: {singlePreview.live_send_available ? "yes" : "no"}.</small>
        <div className="sandbox-grid" aria-label="Preview policy checks">
          {Object.entries(singlePreview.policy_checks || {}).map(([key, value]) => <span key={key}><strong>{key.replaceAll("_", " ")}</strong> {value ? "OK" : "Blocked"}</span>)}
        </div>
      </div>}
      {singleApproval && <div className="state-card success"><h3>Approval request created</h3><p>Approval {singleApproval.approval_request_id}. Provider execution {singleApproval.provider_execution_id}. Approval status {singleApprovalStatus || "pending"}.</p><Link className="button button--light" to={`/approvals?request=${encodeURIComponent(singleApproval.approval_request_id)}`}>Open approval</Link></div>}
    </section>}
    {state === "ready" && items.length === 0 && <div className="state-card"><h2>No imported email</h2><p>Use the authenticated test-import API to add one development message.</p></div>}
    {state === "ready" && items.length > 0 && <div className="table-wrap"><table><thead><tr><th>Sender</th><th>Subject</th><th>Received</th><th>Workflow</th><th>Approval</th><th>Delivery</th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td><strong>{item.sender_name || item.sender_email}</strong><small>{item.sender_email}</small></td><td><Link to={`/email/${item.id}`}>{item.subject || "(No subject)"}</Link></td><td>{new Date(item.received_at).toLocaleString()}</td><td>{item.proposal_status || item.status}</td><td>{item.approval_status || "Not requested"}</td><td>{item.send_status || "Not sent"}</td></tr>)}</tbody></table></div>}
    {state === "ready" && <section className="activity-panel"><div className="section-heading"><div><p className="eyebrow">Mock provider</p><h2>Email campaigns</h2></div></div>
      {campaigns.length === 0 ? <div className="activity-empty"><p>No mock campaigns available.</p></div> : <div className="table-wrap"><table><thead><tr><th>Campaign</th><th>Status</th><th>Audience</th><th>Sent</th><th>Replies</th><th>Updated</th></tr></thead><tbody>{campaigns.map(item => <tr key={item.id}><td><strong>{item.name}</strong><small>{item.provider_key} / {item.external_campaign_id}</small></td><td>{item.status}</td><td>{item.audience_count}</td><td>{item.sent_count}</td><td>{item.reply_count}</td><td>{new Date(item.updated_at).toLocaleString()}</td></tr>)}</tbody></table></div>}
    </section>}
  </section>;
}
