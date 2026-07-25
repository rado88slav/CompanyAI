import { useCallback, useEffect, useState } from "react";
import { emailApi } from "../api/email";
import type { AuditEvent } from "../types/email";

export function AuditPage() {
  const [items, setItems] = useState<AuditEvent[]>([]); const [error, setError] = useState("");
  const load = useCallback(() => emailApi.audit().then(v => {setItems(v.items); setError("");}).catch(() => setError("Audit activity is currently unavailable.")), []);
  useEffect(() => { void load(); }, [load]);
  return <section className="module-page"><div className="page-heading"><div><p className="eyebrow">Traceability</p><h1>Audit log</h1><p>Safe workflow metadata only. Message bodies and credentials are excluded.</p></div><button onClick={() => void load()}>Refresh</button></div>
    {error && <p role="alert" className="error-text">{error}</p>}{!error && items.length === 0 && <div className="state-card">No audit events recorded.</div>}
    {items.length > 0 && <div className="table-wrap"><table><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Resource</th><th>Outcome</th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td>{new Date(item.created_at).toLocaleString()}</td><td>{item.actor_type}</td><td>{item.action}</td><td>{item.resource_type}<small>{item.resource_id}</small></td><td>{item.action.endsWith(".failed") ? "Failed" : "Recorded"}</td></tr>)}</tbody></table></div>}
  </section>;
}
