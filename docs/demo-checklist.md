# Demo Checklist — Document Classification Service

A step-by-step walkthrough for demonstrating the full pipeline.

---

## Pre-Demo Setup (5 min)

Run before the demo audience arrives:

```bash
# 1. Start from clean state
make clean

# 2. Full setup (builds, migrates, seeds everything)
make setup
```

Verify services are healthy:
```bash
docker compose ps             # All 10 services show "healthy"
curl http://localhost:8000/health/live   # {"status":"ok"}
```

Open these tabs in your browser (keep them ready):
| Tab | URL | Purpose |
|-----|-----|---------|
| **Frontend** | http://localhost:5173 | Main demo UI |
| **API Docs** | http://localhost:8000/docs | Swagger (fallback) |
| **pgAdmin** | http://localhost:5050 | Show DB tables (optional) |
| **MinIO Console** | http://localhost:9001 | Show object storage (optional) |

Prepare a demo TIFF file:
```bash
# Use the golden-set TIFF from tests, or any valid TIFF
cp backend/tests/data/golden_tiff.tiff demo_upload.tiff
```

---

## Demo Flow (10 min)

### Scene 1 — Login and Dashboard (2 min)

**Show:** The frontend login page, authentication, role-based dashboard.

1. Open http://localhost:5173
2. You see the login page — clean, simple
3. Log in as: `admin@example.com` / `admin`
4. Dashboard loads — shows Overview tab
5. "Currently no predictions — the system is empty"
6. Explain: this is the internal tool for reviewing classified documents

**Talking point:** "This is what admins and reviewers see. The scanner vendor never sees this — they only interact via SFTP."

---

### Scene 2 — SFTP File Drop (1 min)

**Show:** The vendor's side — just drag a file into the SFTP folder.

1. Show the `sftp_drop/` folder — currently empty
2. Copy the demo TIFF into it:
   ```bash
   cp demo_upload.tiff sftp_drop/
   ```
3. "That's it. The vendor just drops files here via any SFTP client."
4. Optionally demo an SFTP connection:
   ```bash
   sftp -P 2222 vendor@localhost <<< "put demo_upload.tiff drop/"
   ```
   (enter password: `vendorpass`)

**Talking point:** "No API key, no login, no web UI. The vendor uses whatever SFTP client their scanner supports."

---

### Scene 3 — Ingestion Worker Detects the File (1 min)

**Show:** The ingestion worker logs auto-detecting the file.

1. Watch the worker logs:
   ```bash
   docker compose logs -f ingestion-worker
   ```
2. Within 5 seconds, you'll see:
   ```
   [INFO] Polling SFTP directory: drop
   [INFO] New file detected: demo_upload.tiff
   [INFO] Stable file detected: demo_upload.tiff
   [INFO] Valid TIFF confirmed
   [INFO] Uploading original to MinIO: originals/<uuid>.tiff
   [INFO] Enqueued classification job for document <uuid>
   ```

**Talking point:** "The ingestion worker polls every 5 seconds. It waits for files to stop growing before processing — handles slow scanner uploads without reading partial files."

---

### Scene 4 — Inference Worker Classifies (1 min)

**Show:** The ConvNeXt model classifying the document.

1. Watch the inference worker logs:
   ```bash
   docker compose logs -f inference-worker
   ```
2. Within seconds:
   ```
   [INFO] Worker listening on queue: classification
   [INFO] Running classification job: <uuid>
   [INFO] Loading model from classifier.pt
   [INFO] Inference complete — predicted: letter (confidence: 0.89)
   [INFO] Overlay generated and uploaded to MinIO
   [INFO] Classification job succeeded
   ```

**Talking point:** "The model runs on CPU (no GPU needed for this throughput). It classifies into 16 document types — letter, form, email, invoice, resume, etc. The ConvNeXt Tiny model achieves 71.6% top-1 accuracy on this dataset."

---

### Scene 5 — View Results in Frontend (2 min)

**Show:** The classified document appearing in the dashboard.

1. Go back to the browser at http://localhost:5173
2. Refresh the Overview page — predictions now appear
3. Show the predicted class and confidence score
4. Click the **Predictions** tab — see all predictions with filters
5. Click a prediction to see detail:
   - Predicted class with confidence bar
   - Full class scores (all 16 classes with probabilities)
   - Overlay image (original TIFF with class label annotated on top)
6. Click the overlay thumbnail to view full annotated image

**Talking point:** "Every prediction is preserved — original model output is never overwritten. If a reviewer relabels, it's recorded as a separate field, keeping full audit trail."

---

### Scene 6 — API & Swagger (1 min)

**Show:** The REST API with auto-generated documentation.

1. Open http://localhost:8000/docs
2. Show the authenticated endpoints:
   - `GET /batches` — list batches (try it, see the batch created from Scene 2)
   - `GET /predictions/{id}/overlay` — stream the annotated PNG
   - `GET /audit-events` — immutable audit log
3. Copy a Bearer token from frontend (or login via Swagger's Authorize button)
4. Execute a few endpoints to show live data

**Talking point:** "Full OpenAPI spec. The API never performs inference itself — it's purely for review, audit, and user management. Classification is async via background workers."

---

### Scene 7 — Audit Trail (1 min)

**Show:** Every action is recorded.

1. In the frontend, navigate to the **Audit** tab (admin role)
2. Show the audit events table:
   - `USER_CREATED` — admin account
   - `DOCUMENT_INGESTED` — the TIFF we dropped
   - `CLASSIFICATION_ATTEMPTED` — inference job
   - `CLASSIFICATION_SUCCEEDED` — successful prediction
3. Filter by event type, date range, or user

**Talking point:** "Immutable audit log. Every operation — user management, document ingestion, classification, review — is recorded with timestamp, actor, and event detail."

---

### Scene 8 — Reviewer Relabeling (1 min)

**Show:** Low-confidence predictions can be reviewed and corrected.

1. If a prediction has confidence < 0.7 (review_eligible = true):
   - Switch to the Reviewer tab
   - The prediction appears in the review queue
   - Select a new class from the dropdown
   - Submit — the `review_label` field is set, original prediction preserved
2. Check the audit log — a `PREDICTION_REVIEWED` event is recorded

**Talking point:** "Only low-confidence predictions can be re-labeled. The original model output is immutable — we add a reviewer correction field. Confidence threshold is configurable."

---

## Cleanup After Demo

```bash
make clean
```

---

## Backup Talking Points

**Architecture:**
- 10 Docker services on a single machine
- SFTP is the ONLY file entry point — no file upload API endpoint
- Workers run independently — if one crashes, `restart: unless-stopped` brings it back
- CPU-only inference — no GPU hardware dependency

**Model:**
- ConvNeXt Tiny trained on RVL-CDIP (16 document layout classes)
- v2 model: 71.6% top-1 accuracy (up from 61.5% in v1)
- Trained on 50% train fraction — room to improve by training on full dataset

**Security:**
- All credentials in HashiCorp Vault (dev mode for local dev)
- Casbin RBAC: admin, reviewer, auditor roles
- JWT Bearer token authentication (fastapi-users)
- No credentials hardcoded in application code

**Scale:**
- Ingestion worker can be horizontally scaled (multiple containers polling different SFTP folders)
- Inference workers can be scaled by running more RQ consumers
- MinIO is S3-compatible — trivially swap to AWS S3, Azure Blob, or GCS in production

---

## Demo Script (Condensed)

```
1. Show login page → log in as admin
2. Drop TIFF into sftp_drop/
3. Show ingestion worker logs: "Stable file detected" → "Enqueued"
4. Show inference worker logs: "Classification complete" → class + confidence
5. Refresh frontend → prediction appears with confidence and overlay
6. Show Swagger docs → execute /batches, /predictions/{id}/overlay
7. Show audit tab → full event trail
8. (Optional) Reviewer relabel flow
```

## Troubleshooting During Demo

| Symptom | Quick Fix |
|---------|-----------|
| Frontend shows demo mode (no data) | API or backend unhealthy. Check `docker compose ps`. Restart: `docker compose restart api`. |
| TIFF not detected by worker | File still copying? Wait 15 seconds. Or file not actually a TIFF — check magic bytes. |
| Worker crashes on startup | Missing Vault secrets. Run `make seed` again. |
| Overlay image broken / 404 | MinIO bucket not created. Check MinIO console at :9001. |
| Auth 403 on all endpoints | Casbin policies not seeded. Run `make seed-all`. |
| Port conflict | Something already running on 5432/6379/8000. `docker compose down` first. |
