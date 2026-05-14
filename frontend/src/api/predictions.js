import { apiRequest, apiUrl, getToken } from "./client";

export async function fetchRecentPredictions({ reviewEligible, limit = 50 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (reviewEligible !== undefined) {
    params.set("review_eligible", String(reviewEligible));
  }
  return apiRequest(`/predictions/recent?${params.toString()}`);
}

export async function fetchPrediction(predictionId) {
  return apiRequest(`/predictions/${predictionId}`);
}

export async function getPredictionOverlay(predictionId) {
  const headers = new Headers();
  const token = getToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(apiUrl(`/predictions/${predictionId}/overlay`), {
    headers,
  });

  if (!response.ok) {
    const error = new Error(`Could not load overlay: HTTP ${response.status} ${response.statusText || ""}`.trim());
    error.status = response.status;
    throw error;
  }

  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

export async function reviewPrediction(predictionId, reviewedLabel) {
  return apiRequest(`/predictions/${predictionId}/review`, {
    method: "POST",
    body: JSON.stringify({ reviewed_label: reviewedLabel }),
  });
}
