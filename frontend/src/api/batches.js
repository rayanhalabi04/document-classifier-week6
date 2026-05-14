import { apiRequest } from "./client";

export async function listBatches() {
  return apiRequest("/batches");
}

export async function getBatch(batchId) {
  return apiRequest(`/batches/${batchId}`);
}
