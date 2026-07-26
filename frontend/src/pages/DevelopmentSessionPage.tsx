import { FormEvent, useState } from "react";

import { clearSessionContext, saveSessionContext } from "../api/client";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

type Props = {
  onReady: () => void;
};

export function DevelopmentSessionPage({ onReady }: Props) {
  const [token, setToken] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  function submit(event: FormEvent) {
    event.preventDefault();
    const trimmedToken = token.trim();
    const trimmedCompanyId = companyId.trim();
    if (!trimmedToken || !UUID_PATTERN.test(trimmedCompanyId)) {
      setError("A bearer token and valid company UUID are required.");
      return;
    }
    saveSessionContext(trimmedToken, trimmedCompanyId);
    setToken("");
    setSaved(true);
    setError("");
    onReady();
  }

  function clear() {
    clearSessionContext();
    setToken("");
    setCompanyId("");
    setSaved(false);
    setError("");
  }

  return (
    <section className="module-page session-setup">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Development authentication setup</p>
          <h1>Browser session</h1>
          <p>Store local development request context for this browser tab.</p>
        </div>
      </div>
      <form className="workflow-card" onSubmit={submit}>
        <label>
          Administrator bearer token
          <input
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            autoComplete="off"
            required
          />
        </label>
        <label>
          Active company ID
          <input
            value={companyId}
            onChange={(event) => setCompanyId(event.target.value)}
            autoComplete="off"
            required
          />
        </label>
        <div className="actions">
          <button>Save session</button>
          <button type="button" className="button--light" onClick={clear}>Clear session</button>
        </div>
        {saved && <p role="status" className="success">Session saved. Token hidden.</p>}
        {error && <p role="alert" className="error-text">{error}</p>}
      </form>
    </section>
  );
}
