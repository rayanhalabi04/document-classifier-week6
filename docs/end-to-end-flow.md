# Document Classification Service — How It Works

A **scanner vendor** (e.g., a company digitizing paper documents for a law firm, hospital, or government agency) has a physical scanner that converts paper into grayscale TIFF images. They drop files into an SFTP folder. The system detects them, classifies each document into one of 16 RVL-CDIP layout classes, and exposes an authenticated API for review and audit.

---

## The Complete Flow

```
┌──────────┐    SFTP     ┌───────────────┐    RQ     ┌──────────────┐
│ Scanner  │──────────►  │  Ingestion    │─────────► │  Inference   │
│ Vendor   │  drop TIFF  │  Worker       │  enqueue  │  Worker      │
└──────────┘             └───┬───┬───────┘           └──┬──┬──────┬─┘
                             │   │                      │  │      │
                        ┌────┘   └────┐            ┌────┘  │      │
                        ▼             ▼            ▼       ▼      ▼
                     MinIO        Postgres      Postgres  MinIO  Redis
                   (originals)   (documents,   (predict,  (over-  (cache)
                                  batches,      jobs)      lays)
                                  audit)
                                                          │
                                                          ▼
                                             ┌───────────────────┐
                                             │  FastAPI          │
                                             │  (Web UI / API)   │
                                             │                   │
                                             │  Admin logs in    │
                                             │  Sees batches     │
                                             │  Views predictions│
                                             │  Reviewer relabels│
                                             │  Auditor reads log│
                                             └───────────────────┘
```

---

## Step 1 — Vendor Drops TIFFs via SFTP

The vendor uses any SFTP client to connect to `sftp://vendor@sftp:22` with username `vendor` / password `vendorpass`. They drag-and-drop grayscale TIFF files into the `drop/` folder. That's their entire interaction with the system.

**No login, no web UI, no API call.** The FastAPI API deliberately has no file upload endpoint — the spec states "API never performs inference" and "no endpoint for uploading scanner documents."

---

## Step 2 — Ingestion Worker Detects New Files

The ingestion worker (`app/workers/ingestion_worker.py`) runs in a background loop, polling the SFTP folder every 5 seconds via the SFTP adapter (`app/infra/sftp.py`):

```
┌─────────────────────────────────────────────────┐
│ Ingestion Worker (loop)                         │
│                                                 │
│  1. list_files("drop")  → via SFTP adapter      │
│  2. For each file:                              │
│     - Is it "stable"?                           │
│       (size + modified timestamp unchanged      │
│        across two poll cycles)                  │
│     - If stable → process (Step 3)              │
│     - If still changing → record, retry later   │
│  3. Sleep 5 seconds → repeat                    │
└─────────────────────────────────────────────────┘
```

**Stable-file detection:** If the scanner writes a 200 MB TIFF slowly, the first poll sees `size=50 MB`. Second poll: `size=100 MB` — still growing, skip. Third poll: `size=200 MB, mtime unchanged` — stable! Now process.

---

## Step 3 — Validate, Upload, Enqueue

For each stable file, the worker calls `IngestionService.ingest_file()`:

```
1. Validate TIFF magic bytes (first 4 bytes must be "II*\x00" or "MM\x00*")
   → If NOT a valid TIFF: mark_failed(), record audit event, skip

2. Compute SHA-256 checksum of the file content
   → If source_path + checksum combo already exists: duplicate → skip

3. Create or reuse a Batch record (groups documents by source directory)

4. Upload original TIFF to MinIO "originals" bucket
   → Object key: originals/{document_uuid}.tiff

5. Enqueue an RQ job on the Redis "classification" queue
   → Payload: document_id + model_metadata_id

6. Create ClassificationJob record in Postgres (status: queued)

7. Commit transaction, write audit event, invalidate batch list caches
```

---

## Step 4 — Inference Worker Classifies the TIFF

The inference worker (`app/workers/inference_worker.py`) listens on the `classification` RQ queue:

```
1. Receives RQ job: ("document-uuid-abc", "model-metadata-uuid-def")
2. Marks classification_job as "running"
3. Downloads original TIFF from MinIO "originals" bucket
4. Loads ConvNeXt Tiny model from classifier.pt (107 MB)
5. Preprocesses the TIFF:
   - Resize to 224×224 pixels
   - Grayscale → RGB (replicate single channel 3 times)
   - ImageNet normalization:
     mean = [0.485, 0.456, 0.406]
     std  = [0.229, 0.224, 0.225]
6. Runs inference → raw logits → softmax → 16 class probabilities
7. Picks top-1 predicted class (e.g., "email", confidence 0.98)
8. Persists prediction to Postgres:
   - predicted_class: "email"
   - top1_confidence: 0.98
   - class_scores: {"letter": 0.001, "email": 0.98, "form": 0.002, ...}
   - review_eligible: False (confidence ≥ 0.7 means not reviewable)
9. Generates overlay PNG (annotated TIFF with predicted class label drawn on top)
10. Uploads overlay PNG to MinIO "overlays" bucket
11. Marks classification_job as "succeeded"
12. Invalidates batch + prediction + audit caches
```

**The 16 RVL-CDIP classes:** letter, form, email, handwritten, advertisement, scientific report, scientific publication, specification, file folder, news article, budget, invoice, presentation, questionnaire, resume, memo.

---

## Step 5 — Users Interact via the FastAPI Web API

Classified documents are now available through authenticated API endpoints. Three roles exist:

| Role | Permissions |
|------|------------|
| **Admin** | Invite users, assign roles, view batches, view predictions, view audit log, relabel predictions |
| **Reviewer** | View batches, view predictions, relabel low-confidence predictions (confidence < 0.7) |
| **Auditor** | View batches, view predictions, view audit log (read-only) |

### API Endpoints

| Endpoint | Method | Who | Purpose |
|----------|--------|-----|---------|
| `/auth/jwt/login` | POST | Public | Sign in, receive JWT token |
| `/users/me` | GET | Authenticated | View own profile and roles |
| `/users` | GET | Admin | List all users |
| `/users/invitations` | POST | Admin | Invite a new user |
| `/users/{user_id}/roles` | PUT | Admin | Replace user roles |
| `/batches` | GET | Admin, Reviewer, Auditor | List document batches |
| `/batches/{batch_id}` | GET | Admin, Reviewer, Auditor | View batch detail |
| `/predictions/recent` | GET | Admin, Reviewer, Auditor | List recent predictions (filterable by review_eligible) |
| `/predictions/{id}` | GET | Admin, Reviewer, Auditor | View prediction detail (class, confidence, class_scores, overlay key) |
| `/predictions/{id}/overlay` | GET | Admin, Reviewer, Auditor | Stream the annotated overlay PNG from MinIO |
| `/predictions/{id}/review` | POST | Reviewer | Relabel a low-confidence prediction |
| `/audit-events` | GET | Admin, Auditor | List audit events with filters |
| `/health/live` | GET | Public | Liveness check |
| `/health/ready` | GET | Public | Readiness check for all dependencies |

---

## Architecture Layers

| Layer | Files | Responsibility |
|-------|-------|---------------|
| **API** | `app/api/*.py` | HTTP routers only — no business logic, no inference |
| **Services** | `app/services/*.py` | Business logic, transactions, cache invalidation, commit boundaries |
| **Repositories** | `app/repositories/*.py` | SQL-only data access — no business logic, no cache |
| **Domain** | `app/domain/*.py` | Pydantic models, enums, typed errors — no external dependencies |
| **Infrastructure** | `app/infra/*.py` | Adapters for MinIO, SFTP, Vault, Redis, RQ, Casbin, DB sessions, logging |
| **Workers** | `app/workers/*.py` | Background processes: ingestion (SFTP poller) and inference (RQ consumer) |
| **Classifier** | `app/classifier/*.py` | ConvNeXt model loading, preprocessing, inference, overlays, golden replay |
| **Data** | `app/db/*.py` | SQLAlchemy ORM models, session factory, Alembic migrations |

---

## Database Tables

| Table | Purpose |
|-------|---------|
| `users` | Internal accounts with hashed passwords |
| `role_assignments` | User-to-role mappings (admin, reviewer, auditor) |
| `casbin_rule` | Casbin RBAC policy storage |
| `batches` | Groups of ingested documents |
| `documents` | Source TIFF metadata and MinIO blob location |
| `classification_jobs` | RQ job lifecycle tracking |
| `model_metadata` | Classifier identity and 16-class label contract |
| `predictions` | Model output (class, confidence, class_scores) and reviewer corrections |
| `overlay_assets` | Annotated PNG location in MinIO |
| `audit_events` | Immutable operational/security event log |

---

## Services (Docker Compose)

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `postgres` | `postgres:16` | 5432 | Relational database for all persistent data |
| `redis` | `redis:7` | 6379 | RQ job broker + fastapi-cache2 backend |
| `minio` | `minio/minio` | 9000/9001 | Object storage for original TIFFs and overlay PNGs |
| `vault` | `hashicorp/vault:latest` | 8200 | Secrets management (JWT key, DB creds, MinIO keys, SFTP creds) |
| `sftp` | `atmoz/sftp:alpine` | 2222 | Vendor SFTP drop folder |
| `api` | `build: backend/` | 8000 | FastAPI HTTP server |
| `ingestion-worker` | `build: backend/` | — | SFTP polling → MinIO upload → RQ enqueue |
| `inference-worker` | `build: backend/` | — | RQ consumer → ConvNeXt classification → prediction persistence |
| `pgadmin` | `dpage/pgadmin4:latest` | 5050 | Web-based Postgres admin (login: admin@example.com / admin) |

---

## Key Design Decisions

- **SFTP is the ONLY file entry point.** No file upload in the API. Scanner vendors don't have API accounts — they just access the SFTP drop folder.
- **API never runs inference.** All classification is async via RQ workers. Keeps the API fast and predictable regardless of document volume.
- **Stable-file detection prevents partial reads.** The worker compares file size and mtime across poll cycles before ingesting.
- **Original predictions are preserved.** When a reviewer relabels, the original `predicted_class` and `top1_confidence` are never overwritten — a new `review_label` field is set.
- **Confidence threshold is 0.7.** Predictions below 0.7 are flagged `review_eligible = True`. Above 0.7, reviewer relabeling is rejected.
- **All local.** Everything runs in Docker Compose on one machine. No cloud dependencies.
- **No frontend is included.** The project exposes REST API endpoints. A frontend team (or future sprint) would build the UI. Current testing uses `curl` or the browser address bar.
