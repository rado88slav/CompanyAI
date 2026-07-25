import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { emailApi } from "../api/email";
import type { EmailApproval } from "../types/email";

export function ApprovalsPage() {
  const [items, setItems] = useState<EmailApproval[]>([]); const [error, setError] = useState(""); const [busy, setBusy] = useState("");
  const load = useCallback(() => emailApi.approvals().then(v => {setItems(v.items); setError("");}).catch(() => setError("Approvals are currently unavailable.")), []);
  useEffect(() => { void load(); }, [load]);
  async function decide(item: EmailApproval, decision: "approve"|"deny") { setBusy(item.id); try { await (decision === "approve" ? emailApi.approve(item.id) : emailApi.deny(item.id)); await load(); } catch { setError("The approval decision could not be recorded."); } finally { setBusy(""); } }
  return <section className="module-page"><div className="page-heading"><div><p className="eyebrow">Human control</p><h1>Email approvals</h1><p>Review the exact recipient, subject and body before deciding.</p></div><button onClick={() => void load()}>Refresh</button></div>
    {error && <p role="alert" className="error-text">{error}</p>}
    {!error && items.length === 0 && <div className="state-card"><h2>No email approvals</h2></div>}
    <div className="approval-grid">{items.map(item => <article className="workflow-card" key={item.id}><div className="page-heading"><h2>{item.subject}</h2><span className="status-pill">{item.status}</span></div><p>To: <strong>{item.recipient_email}</strong></p><p>Requested action: {item.requested_action}</p><p>Requester: {item.requester_administrator_id || "System"}</p><p>Created: {new Date(item.created_at).toLocaleString()}</p><p>Origin: <Link to={`/email/${item.inbound_email_id}`}>{item.inbound_subject}</Link></p><pre>{item.body}</pre>{item.status === "pending" && <div className="actions"><button disabled={busy === item.id} onClick={() => void decide(item, "approve")}>Approve exact reply</button><button className="danger" disabled={busy === item.id} onClick={() => void decide(item, "deny")}>Reject</button></div>}</article>)}</div>
  </section>;
}
