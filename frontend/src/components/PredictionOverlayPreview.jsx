import { useEffect, useState } from "react";
import { getPredictionOverlay } from "../api/predictions";

export default function PredictionOverlayPreview({ predictionId }) {
  const [overlay, setOverlay] = useState({ status: "loading", url: "", message: "" });

  useEffect(() => {
    let canceled = false;
    let objectUrl = "";

    setOverlay({ status: "loading", url: "", message: "" });

    getPredictionOverlay(predictionId)
      .then((url) => {
        if (canceled) {
          URL.revokeObjectURL(url);
          return;
        }

        objectUrl = url;
        setOverlay({ status: "loaded", url, message: "" });
      })
      .catch((error) => {
        if (canceled) return;

        let message = "Could not load overlay preview";
        if (error.status === 404) {
          message = "No overlay available";
        } else if (error.status === 401 || error.status === 403) {
          message = "Not authorized to view overlay";
        } else if (error.message) {
          message = error.message;
        }

        setOverlay({ status: "error", url: "", message });
      });

    return () => {
      canceled = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [predictionId]);

  return (
    <div className="overlay-box">
      {overlay.status === "loaded" ? (
        <img alt="Prediction overlay preview" src={overlay.url} />
      ) : (
        <span>{overlay.status === "loading" ? "Loading overlay preview..." : overlay.message}</span>
      )}
    </div>
  );
}
