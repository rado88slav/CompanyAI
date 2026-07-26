import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { emailApi } from "../api/email";
import type { EmailCampaign, InboundEmail } from "../types/email";

export function EmailInboxPage() {
  const [items, setItems] = useState<InboundEmail[]>([]);
  const [campaigns, setCampaigns] = useState<EmailCampaign[]>([]);
  const [state, setState] = useState<"loading"|"ready"|"error">("loading");
  const load = useCallback(() => {
    setState("loading");
    Promise.all([emailApi.list(), emailApi.campaigns()])
      .then(([emailValue, campaignValue]) => {
        setItems(emailValue.items);
        setCampaigns(campaignValue.items);
        setState("ready");
      })
      .catch(() => setState("error"));
  }, []);
  useEffect(load, [load]);
  return <section className="module-page">
    <div className="page-heading page-heading--split"><div><p className="eyebrow">Email</p><h1>Email Operations</h1><p>Company-scoped inbox, read-only campaigns and restricted sandbox testing.</p></div><div className="heading-actions"><Link className="button button--light" to="/documentation/email-sandbox">Email Sandbox Guide</Link><button onClick={load} disabled={state === "loading"}>Refresh</button></div></div>
    <section className="sandbox-panel">
      <div>
        <p className="eyebrow">Restricted test mode</p>
        <h2>Email Sandbox</h2>
        <p>Outbound email is backend-gated by exact allowlists, approval, duplicate-send protection, quotas and a global emergency stop.</p>
      </div>
      <div className="sandbox-grid" aria-label="Email sandbox safeguards">
        <span><strong>Recipients</strong> Allowlist only</span>
        <span><strong>Per message</strong> 1 recipient</span>
        <span><strong>Hourly</strong> 5 messages</span>
        <span><strong>Daily</strong> 10 messages</span>
        <span><strong>Approval</strong> Required</span>
        <span><strong>Follow-ups</strong> Disabled</span>
      </div>
      <div className="sandbox-stop" aria-label="Emergency stop status">
        <strong>Emergency stop</strong>
        <span>Backend enforced</span>
      </div>
    </section>
    {state === "loading" && <div className="state-card">Loading inbound email…</div>}
    {state === "error" && <div className="state-card error"><h2>Inbox unavailable</h2><button onClick={load}>Retry</button></div>}
    {state === "ready" && items.length === 0 && <div className="state-card"><h2>No imported email</h2><p>Use the authenticated test-import API to add one development message.</p></div>}
    {state === "ready" && items.length > 0 && <div className="table-wrap"><table><thead><tr><th>Sender</th><th>Subject</th><th>Received</th><th>Workflow</th><th>Approval</th><th>Delivery</th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td><strong>{item.sender_name || item.sender_email}</strong><small>{item.sender_email}</small></td><td><Link to={`/email/${item.id}`}>{item.subject || "(No subject)"}</Link></td><td>{new Date(item.received_at).toLocaleString()}</td><td>{item.proposal_status || item.status}</td><td>{item.approval_status || "Not requested"}</td><td>{item.send_status || "Not sent"}</td></tr>)}</tbody></table></div>}
    {state === "ready" && <section className="activity-panel"><div className="section-heading"><div><p className="eyebrow">Mock provider</p><h2>Email campaigns</h2></div></div>
      {campaigns.length === 0 ? <div className="activity-empty"><p>No mock campaigns available.</p></div> : <div className="table-wrap"><table><thead><tr><th>Campaign</th><th>Status</th><th>Audience</th><th>Sent</th><th>Replies</th><th>Updated</th></tr></thead><tbody>{campaigns.map(item => <tr key={item.id}><td><strong>{item.name}</strong><small>{item.provider_key} / {item.external_campaign_id}</small></td><td>{item.status}</td><td>{item.audience_count}</td><td>{item.sent_count}</td><td>{item.reply_count}</td><td>{new Date(item.updated_at).toLocaleString()}</td></tr>)}</tbody></table></div>}
    </section>}
  </section>;
}
