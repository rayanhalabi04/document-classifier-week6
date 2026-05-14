import { useEffect, useState } from "react";
import { fetchUsers, inviteUser, replaceUserRoles } from "../api/admin";
import { fetchAuditEvents } from "../api/audit";
import RoleBadge from "../components/RoleBadge";
import { demoAuditEvents, demoUsers } from "../demoData";

const roles = ["admin", "reviewer", "auditor"];

export default function AdminPage({ data, demoMode, setDemoMode }) {
  const [users, setUsers] = useState([]);
  const [auditEvents, setAuditEvents] = useState(data.auditEvents);
  const [inviteEmail, setInviteEmail] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    Promise.allSettled([fetchUsers(), fetchAuditEvents({ limit: 5 })]).then(([usersResult, auditResult]) => {
      const failed = usersResult.status === "rejected" || auditResult.status === "rejected";
      setDemoMode(failed || demoMode);
      setUsers(usersResult.status === "fulfilled" ? usersResult.value : demoUsers);
      setAuditEvents(auditResult.status === "fulfilled" ? auditResult.value : demoAuditEvents);
    });
  }, []);

  async function toggleRole(user, role) {
    const nextRoles = user.roles?.includes(role)
      ? user.roles.filter((existing) => existing !== role)
      : [...(user.roles || []), role];
    setUsers((current) => current.map((item) => (item.id === user.id ? { ...item, roles: nextRoles } : item)));
    try {
      await replaceUserRoles(user.id, nextRoles);
      setMessage("Role updated. Permissions are checked on the next API call without requiring logout.");
    } catch (err) {
      setMessage(`Role update is in demo mode: ${err.message}`);
      setDemoMode(true);
    }
  }

  async function handleInvite(event) {
    event.preventDefault();
    if (!inviteEmail) return;
    try {
      const invited = await inviteUser(inviteEmail);
      setUsers((current) => [invited, ...current]);
      setInviteEmail("");
      setMessage("Invitation created.");
    } catch (err) {
      setMessage(`Invite endpoint unavailable for this session: ${err.message}`);
      setDemoMode(true);
    }
  }

  return (
    <div className="page-stack">
      <section className="card split-card">
        <div>
          <p className="eyebrow">Admin story</p>
          <h2>Manage users and roles</h2>
          <p>
            Role changes are stored through the API and Casbin permissions determine what the next request can do.
          </p>
        </div>
        <form className="inline-form" onSubmit={handleInvite}>
          <input
            value={inviteEmail}
            onChange={(event) => setInviteEmail(event.target.value)}
            type="email"
            placeholder="new.user@example.com"
          />
          <button className="primary-button" type="submit">
            Invite user
          </button>
        </form>
      </section>

      {message ? <div className="info-banner">{message}</div> : null}

      <section className="card">
        <div className="section-heading">
          <h2>User role management</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Email</th>
                <th>Status</th>
                <th>Roles</th>
                <th>Toggle permissions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.email}</td>
                  <td>{user.is_active ? "active" : "inactive"}</td>
                  <td className="role-list">{(user.roles || []).map((role) => <RoleBadge key={role} role={role} />)}</td>
                  <td>
                    <div className="toggle-row">
                      {roles.map((role) => (
                        <label className="check-pill" key={role}>
                          <input
                            checked={user.roles?.includes(role) || false}
                            onChange={() => toggleRole(user, role)}
                            type="checkbox"
                          />
                          {role}
                        </label>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <AuditPreview events={auditEvents} />
    </div>
  );
}

function AuditPreview({ events }) {
  return (
    <section className="card">
      <div className="section-heading">
        <h2>Audit log preview</h2>
      </div>
      <div className="audit-list">
        {events.slice(0, 5).map((event) => (
          <article key={event.id}>
            <strong>{event.action}</strong>
            <span>{event.outcome}</span>
            <small>{formatDate(event.timestamp)}</small>
          </article>
        ))}
      </div>
    </section>
  );
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : "No timestamp";
}
