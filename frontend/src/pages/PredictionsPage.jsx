import { useEffect, useState } from "react";
import PredictionOverlayPreview from "../components/PredictionOverlayPreview";
import { fetchPrediction, fetchRecentPredictions } from "../api/predictions";
import { demoPredictions } from "../demoData";

export default function PredictionsPage({ data, setDemoMode }) {
  const [predictions, setPredictions] = useState(data.predictions);
  const [selected, setSelected] = useState(null);
  const [lookupId, setLookupId] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    fetchRecentPredictions()
      .then(setPredictions)
      .catch(() => {
        setDemoMode(true);
        setPredictions(demoPredictions);
      });
  }, []);

  async function lookup(event) {
    event.preventDefault();
    if (!lookupId) return;
    try {
      setSelected(await fetchPrediction(lookupId));
      setMessage("");
    } catch (err) {
      setMessage(`Could not load prediction: ${err.message}`);
      setDemoMode(true);
    }
  }

  return (
    <div className="page-stack">
      <section className="card split-card">
        <div>
          <p className="eyebrow">Inference results</p>
          <h2>Recent predictions</h2>
        </div>
        <form className="inline-form" onSubmit={lookup}>
          <input value={lookupId} onChange={(event) => setLookupId(event.target.value)} placeholder="Prediction id" />
          <button className="primary-button" type="submit">
            Load detail
          </button>
        </form>
      </section>
      {message ? <div className="info-banner">{message}</div> : null}
      <PredictionsTable predictions={predictions} onSelect={setSelected} />
      {selected ? <PredictionDetail prediction={selected} /> : null}
    </div>
  );
}

export function PredictionsTable({ predictions, onSelect, onReview, readOnly = false }) {
  return (
    <section className="card">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Prediction id</th>
              <th>Source filename</th>
              <th>Predicted class</th>
              <th>Confidence</th>
              <th>Review status</th>
              <th>Created</th>
              {!readOnly ? <th>Action</th> : null}
            </tr>
          </thead>
          <tbody>
            {predictions.length ? (
              predictions.map((prediction) => (
                <tr key={prediction.id} onClick={() => onSelect?.(prediction)}>
                  <td className="mono">{prediction.id}</td>
                  <td>{prediction.source_filename || "n/a"}</td>
                  <td>{prediction.predicted_class}</td>
                  <td>
                    <ConfidenceBadge value={prediction.top1_confidence} />
                  </td>
                  <td>{reviewStatusText(prediction)}</td>
                  <td>{formatDate(prediction.created_at)}</td>
                  {!readOnly ? (
                    <td>
                      {onReview && needsReview(prediction) ? (
                        <button
                          className="table-button"
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            onReview(prediction);
                          }}
                        >
                          Review
                        </button>
                      ) : (
                        <span className="muted">View</span>
                      )}
                    </td>
                  ) : null}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={readOnly ? 6 : 7}>
                  <div className="empty-state">No predictions found yet.</div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function ConfidenceBadge({ value }) {
  const score = Number(value || 0);
  const high = score >= 0.7;
  return <span className={`confidence ${high ? "high" : "low"}`}>{Math.round(score * 100)}%</span>;
}

function PredictionDetail({ prediction }) {
  return (
    <section className="card detail-card">
      <p className="eyebrow">Prediction detail</p>
      <h2>{prediction.source_filename || prediction.id}</h2>
      <div className="detail-grid">
        <span>Predicted class</span>
        <strong>{prediction.predicted_class}</strong>
        <span>Confidence</span>
        <ConfidenceBadge value={prediction.top1_confidence} />
        <span>Review status</span>
        <strong>{reviewStatusText(prediction)}</strong>
      </div>
      <PredictionOverlayPreview predictionId={prediction.id} />
    </section>
  );
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : "n/a";
}

export function needsReview(prediction) {
  return prediction.review_eligible === true && !prediction.review_label;
}

export function reviewStatusText(prediction) {
  if (prediction.review_label) {
    return `Reviewed as ${prediction.review_label}`;
  }
  if (prediction.review_eligible) {
    return "Needs review";
  }
  return "Not eligible";
}
