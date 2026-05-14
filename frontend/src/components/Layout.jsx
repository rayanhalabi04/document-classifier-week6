import RoleBadge from "./RoleBadge";

const navByRole = {
  admin: [
    ["overview", "Overview"],
    ["admin", "Admin"],
    ["predictions", "Predictions"],
    ["audit", "Audit"],
  ],
  reviewer: [
    ["overview", "Overview"],
    ["reviewer", "Reviewer Queue"],
    ["predictions", "Predictions"],
  ],
  auditor: [
    ["overview", "Overview"],
    ["predictions", "Predictions"],
    ["audit", "Audit"],
  ],
  unknown: [
    ["overview", "Overview"],
    ["predictions", "Predictions"],
  ],
};

export function getPrimaryRole(user) {
  const roles = user?.roles || [];
  return roles.includes("admin")
    ? "admin"
    : roles.includes("reviewer")
      ? "reviewer"
      : roles.includes("auditor")
        ? "auditor"
        : "unknown";
}

export default function Layout({ user, activePage, setActivePage, onLogout, demoMode, children }) {
  const role = getPrimaryRole(user);
  const navItems = navByRole[role] || navByRole.unknown;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <div className="brand-mark">DC</div>
          <h1>Document Classifier</h1>
          <p>Internal classification service</p>
        </div>

        <nav className="nav-list" aria-label="Primary navigation">
          {navItems.map(([id, label]) => (
            <button
              className={activePage === id ? "active" : ""}
              key={id}
              type="button"
              onClick={() => setActivePage(id)}
            >
              {label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <p className="eyebrow">JWT authenticated dashboard</p>
            <h2>{pageTitle(activePage)}</h2>
          </div>
          <div className="user-menu">
            <div className="user-copy">
              <strong>{user?.email || "Signed in user"}</strong>
              <RoleBadge role={role} />
            </div>
            <button className="ghost-button" type="button" onClick={onLogout}>
              Logout
            </button>
          </div>
        </header>
        {demoMode ? (
          <div className="demo-banner">Demo data shown because API is unavailable.</div>
        ) : null}
        {children}
      </main>
    </div>
  );
}

function pageTitle(page) {
  const titles = {
    overview: "Overview",
    admin: "Admin workspace",
    reviewer: "Reviewer queue",
    predictions: "Predictions",
    audit: "Audit log",
  };
  return titles[page] || "Overview";
}
