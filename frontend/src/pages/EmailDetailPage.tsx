import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { emailApi } from "../api/email";
import type { InboundEmailDetail } from "../types/email";

export function EmailDetailPage() {
  const { emailId = "" } = useParams();
  const [item, setItem] = useState<InboundEmailDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState({recipient_email: "", subject: "", body: ""});
  const [connectionId, setConnectionId] = useState("");
  const load = useCallback(async () => {
    try {
      const value = await emailApi.detail(emailId); setItem(value);
      setForm(value.reply_proposal ? {recipient_email: value.reply_proposal.recipient_email, subject: value.reply_proposal.subject, body: value.reply_proposal.body} : {recipient_email: value.sender_email, subject: /^re\s*:/i.test(value.subject) ? value.subject : `Re: ${value.subject}`, body: ""});
      const connections = await emailApi.connections();
      setConnectionId(connections.items.find(c => c.provider_key === "local_test_email" && c.status === "active")?.id || "");
      setError("");
    } catch { setError("Email detail is currently unavailable."); }
  }, [emailId]);
  useEffect(() => { void load(); }, [load]);
  async function act(operation: () => Promise<unknown>, message: string) {
    setBusy(true); setError(""); setNotice("");
    try { await operation(); setNotice(message); await load(); } catch { setError("The action could not be completed."); } finally { setBusy(false); }
  }
  function save(event: FormEvent) {
    event.preventDefault();
    if (!item) return;
    void act(() => item.reply_proposal ? emailApi.updateProposal(item.reply_proposal.id, form) : emailApi.createProposal(item.id, form), item.reply_proposal ? "Draft updated." : "Draft created.");
  }
  if (error && !item) return <section className="module-page"><div className="state-card error"><h1>Email unavailable</h1><p>{error}</p><button onClick={() => void load()}>Retry</button></div></section>;
  if (!item) return <section className="module-page"><div className="state-card">Loading email detail…</div></section>;
  const proposal = item.reply_proposal;
  const editable = !proposal || proposal.status === "draft";
  const approved = item.approval_status === "approved";
  return <section className="module-page">
    <Link to="/email">← Back to inbox</Link>
    <div className="page-heading"><div><p className="eyebrow">Inbound message</p><h1>{item.subject || "(No subject)"}</h1><p>From {item.sender_name ? `${item.sender_name} · ` : ""}{item.sender_email} to {item.recipient_email}</p></div><span className="status-pill">{item.status}</span></div>
    <article className="message-card"><time>{new Date(item.received_at).toLocaleString()}</time><pre>{item.body}</pre></article>
    <form className="workflow-card" onSubmit={save}><h2>Reply proposal</h2>
      <label>Recipient<input value={form.recipient_email} onChange={e => setForm({...form, recipient_email: e.target.value})} disabled={!editable || busy} required /></label>
      <label>Subject<input value={form.subject} onChange={e => setForm({...form, subject: e.target.value})} disabled={!editable || busy} /></label>
      <label>Plain-text body<textarea value={form.body} onChange={e => setForm({...form, body: e.target.value})} disabled={!editable || busy} rows={10} required /></label>
      <div className="actions">{editable && <button disabled={busy}>{proposal ? "Update draft" : "Create proposal"}</button>}
      {proposal?.status === "draft" && <button type="button" disabled={busy} onClick={() => void act(() => emailApi.submit(proposal.id), "Approval requested.")}>Request approval</button>}
      <button type="button" className="danger" disabled={busy || !approved || !connectionId || item.send_status === "sent"} onClick={() => { if (window.confirm("Send this exact reply through test delivery?")) void act(() => emailApi.send(proposal!.id, connectionId), "Test delivery completed."); }}>Send test delivery</button></div>
      {!connectionId && <p className="hint">No enabled Local Test Email Provider connection is available. Configuration is not yet available in the dashboard.</p>}
      <p>Approval: <strong>{item.approval_status || "Not requested"}</strong> · Delivery: <strong>{item.send_status || "Not sent"}</strong></p>
      {item.outbound_email?.provider_message_id && <p>Test provider message ID: {item.outbound_email.provider_message_id}</p>}
      {notice && <p role="status" className="success">{notice}</p>}{error && <p role="alert" className="error-text">{error}</p>}
    </form>
  </section>;
}
