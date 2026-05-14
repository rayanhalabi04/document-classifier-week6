import { useEffect, useState } from "react";
import { isNetworkError } from "../api/client";
import { getBatch, listBatches } from "../api/batches";

export default function BatchesPage({ data, setDemoMode }) {
  const [batches, setBatches] = useState(data.batches || []);
  const [selected, setSelected] = useState(null);
  const [lookupId, setLookupId] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadBatches();
  }, []);

  async function loadBatches() {
    try {
      const nextBatches = await listBatches();
      setBatches(nextBatches);
      setDemoMode(false);
      setMessage("");
    } catch (error) {
      handleBatchError(error);
    }
  }

  async function loadBatch(batchId) {
    if (!batchId) return;
    try {
      const batch = await getBatch(batchId);
      setSelected(batch);
      setMessage("");
    } catch (error) {
      handleBatchError(error);
    }
  }

  function handleBatchError(error) {
    if (error.status === 401) {
      setMessage("Session expired or not authenticated.");
      setDemoMode(false);
    } else if (error.status === 403) {
      setMessage("Not allowed to view batches.");
      setDemoMode(false);
    } else if (isNetworkError(error)) {
      setMessage("API unavailable.");
      setDemoMode(true);
    } else {
      setMessage(`Could not load batches: ${error.message}`);
    }
  }

  function submitLookup(event) {
    event.preventDefault();
    loadBatch(lookupId);
  }

  return (
    <div className="page-stack">
      <section className="card split-card">
        <div>
          <p className="eyebrow">Ingestion view</p>
          <h2>Batches</h2>
          <p>A batch is a group/run of documents detected from the SFTP drop and tracked through ingestion and classification.</p>
        </div>
        <form className="inline-form" onSubmit={submitLookup}>
          <input value={lookupId} onChange={(event) => setLookupId(event.target.value)} placeholder="Batch id" />
          <button className="primary-button" type="submit">
            Load detail
          </button>
        </form>
      </section>

      {message ? <div className="info-banner">{message}</div> : null}

      <BatchesTable batches={batches} onSelect={loadBatch} />
      {selected ? <BatchDetail batch={selected} /> : null}
    </div>
  );
}

export function BatchesTable({ batches, onSelect, compact = false }) {
  return (
    <section className="card">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Batch id</th>
              <th>Source</th>
              <th>Status</th>
              <th>Documents</th>
              {!compact ? <th>Reviewable</th> : null}
              <th>Created</th>
              {!compact ? <th>Action</th> : null}
            </tr>
          </thead>
          <tbody>
            {batches.length ? (
              batches.map((batch) => (
                <tr key={batch.id} onClick={() => onSelect?.(batch.id)}>
                  <td className="mono">{batch.id}</td>
                  <td>{batch.source || batch.source_filename || "n/a"}</td>
                  <td>
                    <span className="status-pill">{batch.status || "unknown"}</span>
                  </td>
                  <td>{batch.document_count ?? "n/a"}</td>
                  {!compact ? <td>{batch.reviewable_count ?? "n/a"}</td> : null}
                  <td>{formatDate(batch.created_at)}</td>
                  {!compact ? (
                    <td>
                      <button
                        className="table-button"
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          onSelect?.(batch.id);
                        }}
                      >
                        View
                      </button>
                    </td>
                  ) : null}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={compact ? 5 : 7}>
                  <div className="empty-state">No batches found yet.</div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function BatchDetail({ batch }) {
  return (
    <section className="card detail-card">
      <p className="eyebrow">Batch detail</p>
      <h2>{batch.id}</h2>
      <div className="detail-grid">
        <span>Source</span>
        <strong>{batch.source || batch.source_filename || "n/a"}</strong>
        <span>Status</span>
        <strong>{batch.status || "unknown"}</strong>
        <span>Documents</span>
        <strong>{batch.document_count ?? "n/a"}</strong>
        <span>Reviewable</span>
        <strong>{batch.reviewable_count ?? "n/a"}</strong>
        <span>Created</span>
        <strong>{formatDate(batch.created_at)}</strong>
        <span>Updated</span>
        <strong>{formatDate(batch.updated_at)}</strong>
        <span>Completed</span>
        <strong>{batch.completed_at ? formatDate(batch.completed_at) : "In progress"}</strong>
      </div>
    </section>
  );
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : "n/a";
}
