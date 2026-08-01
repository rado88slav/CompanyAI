import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { emailApi } from "../api/email";
import type { EmailApproval, SingleMessageApprovalReview } from "../types/email";

export function ApprovalsPage() {
  const [searchParams] = useSearchParams();
  const [singleItems, setSingleItems] = useState<SingleMessageApprovalReview[]>([]);
  const [replyItems, setReplyItems] = useState<EmailApproval[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const highlighted = searchParams.get("request");
  const load = useCallback(async () => {
    try {
      const [single, replies] = await Promise.all([
        emailApi.singleMessageApprovals(),
        emailApi.approvals(),
      ]);
      setSingleItems(single.items);
      setReplyItems(replies.items);
      setError("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Approvals are currently unavailable.");
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function decideSingle(item: SingleMessageApprovalReview, decision: "approve" | "deny") {
    if (item.self_approval_blocked) {
      setError("Approval must be completed by another authorized administrator.");
      return;
    }
    setBusy(item.id);
    setError("");
    try {
      if (decision === "approve") await emailApi.approveApprovalRequest(item);
      else await emailApi.denyApprovalRequest(item.id);
      await load();
    } catch (err) {
      const message = err instanceof ApiError && err.status === 403
        ? "Approval must be completed by another authorized administrator."
        : "The approval decision could not be recorded.";
      setError(message);
    } finally {
      setBusy("");
    }
  }

  async function decideReply(item: EmailApproval, decision: "approve" | "deny") {
    setBusy(item.id);
    setError("");
    try {
      await (decision === "approve" ? emailApi.approve(item.id) : emailApi.deny(item.id));
      await load();
    } catch {
      setError("The approval decision could not be recorded.");
    } finally {
      setBusy("");
    }
  }

  return <section className="module-page">
    <div className="page-heading">
      <div><p className="eyebrow">Human control</p><h1>Email approvals</h1><p>Review exact message content before deciding.</p></div>
      <button onClick={() => void load()} disabled={Boolean(busy)}>Refresh</button>
    </div>
    {error && <p role="alert" className="error-text">{error}</p>}
    {singleItems.length === 0 && replyItems.length === 0 && !error && <div className="state-card"><h2>No email approvals</h2></div>}
    <div className="approval-grid">
      {singleItems.map((item) => <article className={`workflow-card ${highlighted === item.id ? "is-highlighted" : ""}`} key={item.id}>
        <div className="page-heading"><h2>{item.subject}</h2><span className="status-pill">{item.mode === "live_test" ? "LIVE TEST" : "Simulation"} · {item.status}</span></div>
        <p>From: <strong>{item.sender_email}</strong></p>
        <p>To: <strong>{item.recipient_email}</strong></p>
        <p>Requested action: {item.requested_action}</p>
        <p>Idempotency key: {item.idempotency_key}</p>
        <p>Digest: {item.payload_digest.slice(0, 12)}…</p>
        <p>Requested: {new Date(item.created_at).toLocaleString()}</p>
        {item.self_approval_blocked && item.status === "pending" && <p className="warning-text">Approval must be completed by another authorized administrator.</p>}
        <pre>{item.body}</pre>
        {item.status === "pending" && <div className="actions">
          <button disabled={busy === item.id || item.self_approval_blocked} onClick={() => void decideSingle(item, "approve")}>Approve exact message</button>
          <button className="danger" disabled={busy === item.id || item.self_approval_blocked} onClick={() => void decideSingle(item, "deny")}>Deny</button>
        </div>}
        {item.status !== "pending" && <p>Status: <strong>{item.status}</strong></p>}
      </article>)}
      {replyItems.map(item => <article className="workflow-card" key={item.id}>
        <div className="page-heading"><h2>{item.subject}</h2><span className="status-pill">{item.status}</span></div>
        <p>To: <strong>{item.recipient_email}</strong></p>
        <p>Requested action: {item.requested_action}</p>
        <p>Requester: {item.requester_administrator_id || "System"}</p>
        <p>Created: {new Date(item.created_at).toLocaleString()}</p>
        <p>Origin: <Link to={`/email/${item.inbound_email_id}`}>{item.inbound_subject}</Link></p>
        <pre>{item.body}</pre>
        {item.status === "pending" && <div className="actions"><button disabled={busy === item.id} onClick={() => void decideReply(item, "approve")}>Approve exact reply</button><button className="danger" disabled={busy === item.id} onClick={() => void decideReply(item, "deny")}>Reject</button></div>}
      </article>)}
    </div>
  </section>;
}
