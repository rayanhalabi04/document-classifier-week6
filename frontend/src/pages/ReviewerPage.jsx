import { useEffect, useState } from "react";
import { fetchRecentPredictions, reviewPrediction } from "../api/predictions";
import PredictionOverlayPreview from "../components/PredictionOverlayPreview";
import { isNetworkError } from "../api/client";
import { demoPredictions } from "../demoData";
import { ConfidenceBadge, PredictionsTable, needsReview } from "./PredictionsPage";

export default function ReviewerPage({ setDemoMode }) {
  const [predictions, setPredictions] = useState([]);
  const [selected, setSelected] = useState(null);
  const [label, setLabel] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadReviewQueue().catch((error) => {
      handleQueueLoadError(error);
    });
  }, []);

  async function loadReviewQueue() {
    const reviewQueue = filterReviewQueue(await fetchRecentPredictions({ reviewEligible: true }));
    setPredictions(reviewQueue);
    setDemoMode(false);
    setMessage("");
    return reviewQueue;
  }

  function handleQueueLoadError(error) {
    logReviewerError("queue load failed", error);
    setMessage(reviewQueueErrorMessage(error));

    if (isNetworkError(error)) {
      setDemoMode(true);
      setPredictions(filterReviewQueue(demoPredictions));
      return;
    }

    setDemoMode(false);
    setPredictions([]);
  }

  function selectPrediction(prediction) {
    setSelected(prediction);
    setLabel("");
  }

  function closeReview() {
    setSelected(null);
    setLabel("");
  }

  async function submitReview(event) {
    event.preventDefault();
    if (!selected || !label) return;
    try {
      const reviewed = await reviewPrediction(selected.id, label);
      try {
        await loadReviewQueue();
      } catch {
        setPredictions((current) =>
          current
            .map((prediction) => (prediction.id === reviewed.id ? { ...prediction, ...reviewed } : prediction))
            .filter((prediction) => prediction.id !== reviewed.id && needsReview(prediction)),
        );
      }
      setMessage("Review submitted.");
      closeReview();
    } catch (err) {
      logReviewerError("review submit failed", err);
      if (err.status === 401) {
        setMessage("Session expired or not authenticated.");
        setDemoMode(false);
      } else if (err.status === 403) {
        setMessage("This user does not have reviewer permission.");
        setDemoMode(false);
      } else if (isNetworkError(err)) {
        setMessage("API unavailable.");
        setDemoMode(true);
      } else {
        setMessage(`Could not submit review: ${err.message}`);
      }
    }
  }

  return (
    <div className="page-stack">
      <section className="card split-card">
        <div>
          <p className="eyebrow">Reviewer workflow</p>
          <h2>Low-confidence prediction queue</h2>
          <p>Only review-eligible predictions appear here. Backend permissions still decide whether relabeling is allowed.</p>
        </div>
      </section>
      {message ? <div className="info-banner">{message}</div> : null}
      <PredictionsTable predictions={predictions} onReview={selectPrediction} />

      {selected ? (
        <div className="modal-backdrop" role="presentation">
          <section className="review-panel" role="dialog" aria-modal="true" aria-label="Review prediction">
            <button className="close-button" type="button" onClick={closeReview}>
              x
            </button>
            <p className="eyebrow">Prediction review</p>
            <h2>{selected.source_filename || selected.id}</h2>
            <div className="detail-grid">
              <span>Predicted class</span>
              <strong>{selected.predicted_class}</strong>
              <span>Confidence</span>
              <ConfidenceBadge value={selected.top1_confidence} />
            </div>
            <PredictionOverlayPreview predictionId={selected.id} />
            <form className="form-stack" onSubmit={submitReview}>
              <label>
                Corrected label
                <input value={label} onChange={(event) => setLabel(event.target.value)} placeholder="invoice" required />
              </label>
              <button className="primary-button" type="submit">
                Submit review
              </button>
            </form>
          </section>
        </div>
      ) : null}
    </div>
  );
}

function reviewQueueErrorMessage(error) {
  if (error.status === 401) {
    return "Session expired or not authenticated.";
  }
  if (error.status === 403) {
    return "This user does not have reviewer permission.";
  }
  if (isNetworkError(error)) {
    return "API unavailable.";
  }
  return `Could not load reviewer queue: ${error.message}`;
}

function filterReviewQueue(predictions) {
  return predictions.filter(needsReview);
}

function logReviewerError(message, error) {
  if (!import.meta.env.DEV) return;
  console.warn(`[reviewer] ${message}`, {
    status: error?.status,
    url: error?.url,
    isNetworkError: isNetworkError(error),
    message: error?.message,
  });
}
