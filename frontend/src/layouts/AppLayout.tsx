import { NavLink, Outlet } from "react-router-dom";

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
          <span className="topbar__mode">Read-only foundation</span>
        </header>
        <main className="content" id="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
