import { NavLink, Outlet } from "react-router-dom";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  clearSessionContext,
  fetchAvailableCompanies,
  fetchCurrentAdministrator,
  hasAccessToken,
  isAuthenticationError,
  login,
  saveCompanyContext,
  selectedCompanyId,
  SESSION_EXPIRED_EVENT,
  type AvailableCompanyContext,
  type Administrator,
} from "../api/client";
import { ActiveCompanyProvider } from "../context/ActiveCompanyContext";

const navigation = [
  { to: "/", label: "Overview", end: true },
  { to: "/agent", label: "Agent Activity" },
  { to: "/providers", label: "Provider Connections" },
  { to: "/email", label: "Email Operations" },
  { to: "/calls", label: "Call Operations" },
  { to: "/approvals", label: "Approvals" },
  { to: "/audit", label: "Audit Log" },
  { to: "/settings", label: "Settings" },
];

type SessionState =
  | { status: "bootstrapping" }
  | { status: "anonymous"; message?: string }
  | { status: "backend-unavailable"; message: string }
  | { status: "empty-companies"; administrator: Administrator }
  | {
      status: "authenticated";
      administrator: Administrator;
      companies: AvailableCompanyContext[];
      activeCompanyId: string;
    };

export function AppLayout() {
  const [session, setSession] = useState<SessionState>({
    status: "bootstrapping",
  });
  const [loginBusy, setLoginBusy] = useState(false);
  const [loginError, setLoginError] = useState("");

  const bootstrap = useCallback(async (signal?: AbortSignal) => {
    if (!hasAccessToken()) {
      setSession({ status: "anonymous" });
      return;
    }
    setSession({ status: "bootstrapping" });
    try {
      const [administrator, companyList] = await Promise.all([
        fetchCurrentAdministrator(signal),
        fetchAvailableCompanies(signal),
      ]);
      if (companyList.items.length === 0) {
        sessionStorage.removeItem("companyai.companyId");
        setSession({ status: "empty-companies", administrator });
        return;
      }
      const savedCompanyId = selectedCompanyId();
      const activeCompany =
        companyList.items.find((item) => item.company.id === savedCompanyId) ??
        companyList.items[0];
      saveCompanyContext(activeCompany.company.id);
      setSession({
        status: "authenticated",
        administrator,
        companies: companyList.items,
        activeCompanyId: activeCompany.company.id,
      });
    } catch (error) {
      if (signal?.aborted) return;
      if (isAuthenticationError(error)) {
        clearSessionContext();
        setSession({
          status: "anonymous",
          message: "Your session expired. Please sign in again.",
        });
        return;
      }
      setSession({
        status: "backend-unavailable",
        message: "The dashboard API is unavailable. Please retry when the backend is reachable.",
      });
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void bootstrap(controller.signal);
    return () => controller.abort();
  }, [bootstrap]);

  useEffect(() => {
    function expireSession() {
      clearSessionContext();
      setSession({
        status: "anonymous",
        message: "Your session expired. Please sign in again.",
      });
    }
    window.addEventListener(SESSION_EXPIRED_EVENT, expireSession);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expireSession);
  }, []);

  function clearSession() {
    clearSessionContext();
    setSession({ status: "anonymous" });
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");
    setLoginBusy(true);
    setLoginError("");
    try {
      await login(email, password);
      await bootstrap();
    } catch (error) {
      if (isAuthenticationError(error)) {
        setLoginError("The email or password is not valid.");
      } else {
        setLoginError(
          "Sign in is unavailable while the backend cannot be reached.",
        );
      }
    } finally {
      setLoginBusy(false);
    }
  }

  function changeCompany(companyId: string) {
    if (session.status !== "authenticated") return;
    const nextCompany = session.companies.find(
      (item) => item.company.id === companyId,
    );
    if (!nextCompany) {
      setSession({
        status: "anonymous",
        message: "Access to that company is not available for this account.",
      });
      clearSessionContext();
      return;
    }
    saveCompanyContext(nextCompany.company.id);
    setSession({ ...session, activeCompanyId: nextCompany.company.id });
  }

  const activeCompany = useMemo(() => {
    if (session.status !== "authenticated") return null;
    return session.companies.find((item) => item.company.id === session.activeCompanyId) ?? null;
  }, [session]);

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brand">
          <span className="brand__mark" aria-hidden="true">C</span>
          <div>
            <strong>CompanyAI</strong>
            <span>Operations console</span>
          </div>
        </div>
        <nav className="navigation">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                isActive ? "navigation__link is-active" : "navigation__link"
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar__footer">
          <span className="eyebrow">Protected workspace</span>
            <span>
              {session.status === "authenticated"
                ? session.administrator.email
                : "Authentication required"}
            </span>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">Business operations</span>
            <p>
              {activeCompany
                ? activeCompany.company.name
                : "Observe systems after selecting an authorized company."}
            </p>
          </div>
          <div className="topbar__actions">
            {session.status === "authenticated" && (
              <label className="company-selector">
                <span>Company</span>
                <select
                  aria-label="Active company"
                  value={session.activeCompanyId}
                  onChange={(event) => changeCompany(event.target.value)}
                >
                  {session.companies.map((item) => (
                    <option key={item.company.id} value={item.company.id}>
                      {item.company.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {session.status === "authenticated" && (
              <button
                type="button"
                className="button button--light"
                onClick={clearSession}
              >
                Logout
              </button>
            )}
          </div>
        </header>
        <main className="content" id="main-content">
          {session.status === "bootstrapping" && (
            <div className="state-panel" role="status">
              <span className="spinner" aria-hidden="true" />
              <div>
                <h2>Loading secure session</h2>
                <p>Checking authentication and company access.</p>
              </div>
            </div>
          )}

          {session.status === "backend-unavailable" && (
            <div className="state-panel state-panel--error" role="alert">
              <div>
                <h2>Backend unavailable</h2>
                <p>{session.message}</p>
              </div>
              <button className="button" type="button" onClick={() => void bootstrap()}>
                Retry
              </button>
            </div>
          )}

          {session.status === "empty-companies" && (
            <div className="state-panel" role="status">
              <div>
                <h2>No companies available</h2>
                <p>This account has no active company memberships.</p>
              </div>
              <button className="button button--light" type="button" onClick={clearSession}>
                Logout
              </button>
            </div>
          )}

          {session.status === "anonymous" && (
            <section className="auth-panel" aria-labelledby="login-title">
              <div>
                <span className="eyebrow">Secure sign in</span>
                <h1 id="login-title">CompanyAI dashboard</h1>
                <p>Use an existing administrator account to continue.</p>
                {session.message && (
                  <p role="alert" className="session-message">
                    {session.message}
                  </p>
                )}
              </div>
              <form className="auth-form" onSubmit={(event) => void handleLogin(event)}>
                <label>
                  <span>Email</span>
                  <input name="email" type="email" autoComplete="username" required />
                </label>
                <label>
                  <span>Password</span>
                  <input name="password" type="password" autoComplete="current-password" required />
                </label>
                {loginError && <p role="alert" className="error-text">{loginError}</p>}
                <button className="button" type="submit" disabled={loginBusy}>
                  {loginBusy ? "Signing in" : "Login"}
                </button>
              </form>
            </section>
          )}

          {session.status === "authenticated" && (
            <ActiveCompanyProvider value={activeCompany}>
              <div key={session.activeCompanyId}>
                <Outlet />
              </div>
            </ActiveCompanyProvider>
          )}
        </main>
      </div>
    </div>
  );
}
