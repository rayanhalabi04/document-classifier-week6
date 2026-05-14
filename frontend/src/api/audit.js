import { apiRequest } from "./client";

export async function fetchAuditEvents({ limit = 50 } = {}) {
  return apiRequest(`/audit-events?limit=${limit}`);
}
