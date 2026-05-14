import { useEffect, useState } from "react";
import { fetchAuditEvents } from "../api/audit";
import { demoAuditEvents } from "../demoData";
import { PredictionsTable } from "./PredictionsPage";

export default function AuditorPage({ data, auditOnly = false, setDemoMode }) {
  const [auditEvents, setAuditEvents] = useState(data.auditEvents);

  useEffect(() => {
    fetchAuditEvents({ limit: 50 })
      .then(setAuditEvents)
      .catch(() => {
        setDemoMode(true);
        setAuditEvents(demoAuditEvents);
      });
  }, []);

  return (
    <div className="page-stack">
      <section className="card split-card">
        <div>
          <p className="eyebrow">Read-only mode</p>
          <h2>Auditor visibility</h2>
          <p>Auditors can inspect predictions and audit events without mutation controls.</p>
        </div>
        <span className="readonly-pill">Read-only mode</span>
      </section>

      {!auditOnly ? (
        <>
          <PredictionsTable predictions={data.predictions} readOnly />
        </>
      ) : null}

      <AuditTable events={auditEvents} />
    </div>
  );
}

export function AuditTable({ events }) {
  return (
    <section className="card">
      <div className="section-heading">
        <h2>Audit log</h2>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Action</th>
              <th>Target</th>
              <th>Outcome</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {events.length ? (
              events.map((event) => (
                <tr key={event.id}>
                  <td>{event.action}</td>
                  <td>{event.target || event.target_type || event.target_id || "n/a"}</td>
                  <td>{event.outcome}</td>
                  <td>{formatDate(event.timestamp)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="4">
                  <EmptyState text="No audit events are visible for this user." />
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function EmptyState({ text }) {
  return <div className="empty-state">{text}</div>;
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : "n/a";
}
