const CONFIGURED_API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const API_BASE_URL = import.meta.env.DEV ? "" : CONFIGURED_API_BASE_URL;
const TOKEN_KEY = "document_classifier_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function apiUrl(path) {
  return `${API_BASE_URL}${path}`;
}

export function isNetworkError(error) {
  return Boolean(error?.isNetworkError);
}

export async function apiRequest(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const hasBody = options.body !== undefined && !(options.body instanceof FormData);
  if (hasBody && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response;
  const url = `${API_BASE_URL}${path}`;
  const method = options.method || "GET";

  logApiRequest(method, url, headers);

  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (error) {
    throw buildNetworkError(error, url, method);
  }

  if (!response.ok) {
    const detail = await readError(response);
    logApiFailure(method, url, response.status, detail);
    const error = new Error(
      `HTTP ${response.status} ${response.statusText || ""}${detail ? `: ${detail}` : ""}`.trim(),
    );
    error.status = response.status;
    error.url = url;
    throw error;
  }

  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response.text();
}

async function readError(response) {
  try {
    const data = await response.json();
    return typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
  } catch {
    return response.statusText;
  }
}

function buildNetworkError(error, url, method) {
  const message = [
    `Network request failed for ${url}.`,
    "If the API is running, this is commonly caused by CORS, a stopped backend, or the wrong VITE_API_BASE_URL.",
    `Browser error: ${error.message}`,
  ].join(" ");
  const wrapped = new Error(message);
  wrapped.cause = error;
  wrapped.isNetworkError = true;
  wrapped.url = url;
  logApiFailure(method, url, "network", error.message);
  return wrapped;
}

function logApiRequest(method, url, headers) {
  if (!import.meta.env.DEV) return;
  console.debug("[api] request", {
    method,
    url,
    hasAuthorizationHeader: headers.has("Authorization"),
  });
}

function logApiFailure(method, url, status, detail) {
  if (!import.meta.env.DEV) return;
  console.warn("[api] request failed", {
    method,
    url,
    status,
    detail,
  });
}
