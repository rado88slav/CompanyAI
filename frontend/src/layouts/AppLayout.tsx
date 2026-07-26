import { NavLink, Outlet } from "react-router-dom";
import { useState } from "react";

import { clearSessionContext, hasSessionContext } from "../api/client";
import { DevelopmentSessionPage } from "../pages/DevelopmentSessionPage";

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

export function AppLayout() {
  const [sessionReady, setSessionReady] = useState(hasSessionContext());
  function clearSession() {
    clearSessionContext();
    setSessionReady(false);
  }
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
          <span className="eyebrow">Local workspace</span>
          <span>Secure operations foundation</span>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">Business operations</span>
            <p>Observe systems without triggering actions.</p>
          </div>
          <div className="topbar__actions">
            <span className="topbar__mode">Development session</span>
            {sessionReady && <button type="button" className="button button--light" onClick={clearSession}>Clear session</button>}
          </div>
        </header>
        <main className="content" id="main-content">
          {sessionReady ? <Outlet /> : <DevelopmentSessionPage onReady={() => setSessionReady(true)} />}
        </main>
      </div>
    </div>
  );
}
