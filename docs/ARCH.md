# Architecture: Internal Document Classification Service

## Overview

A local Docker Compose service that classifies scanned documents into one of
16 RVL-CDIP layout categories using a ConvNeXt Tiny or Small classifier. A
scanner vendor drops grayscale TIFF files into an SFTP server; the system
ingests, classifies, and exposes results through a reviewed API.

The API never runs inference. Inference is isolated in a dedicated worker.

---

## Module Boundaries

```
┌──────────────────────────────────────────────────────────────┐
│                        app/api/                              │
│   HTTP routing only — no business logic, no SQL, no cache    │
│   Depends on: services (via Depends()), domain schemas       │
└────────────────────────┬─────────────────────────────────────┘
                         │ calls
┌────────────────────────▼─────────────────────────────────────┐
│                      app/services/                           │
│   Business logic, transactions, cache invalidation           │
│   Depends on: repositories, infra adapters, domain models    │
└──────────┬──────────────────────────┬────────────────────────┘
           │ SQL only                 │ adapters
┌──────────▼────────────┐  ┌──────────▼────────────────────────┐
│  app/repositories/    │  │         app/infra/                │
│  SELECT/INSERT/UPDATE │  │  db, redis, queue, cache,         │
│  No cache, no logic   │  │  minio, sftp, vault, casbin       │
└──────────┬────────────┘  └───────────────────────────────────┘
           │ ORM models
┌──────────▼────────────┐
│     app/db/           │
│  models.py, session   │
│  SQLAlchemy ORM only  │
└───────────────────────┘

┌───────────────────────┐   ┌───────────────────────────────────┐
│    app/domain/        │   │       app/classifier/             │
│  Enums, error types,  │   │  loader, validation, preprocessing│
│  pure Python only     │   │  inference, overlays, golden      │
│  No imports from app  │   │  No API/service/repo imports      │
└───────────────────────┘   └───────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      app/workers/                           │
│  ingestion_worker.py — SFTP poll → MinIO → RQ enqueue       │
│  inference_worker.py — RQ consume → classify → persist      │
│  Depends on: services, infra, classifier                    │
└─────────────────────────────────────────────────────────────┘
```

### Boundary Rules

| Layer | May import from | Must NOT import from |
|---|---|---|
| `api/` | `services/`, `domain/`, `infra/db` | `repositories/`, `classifier/`, `workers/` |
| `services/` | `repositories/`, `infra/`, `domain/` | `api/`, `workers/` |
| `repositories/` | `db/`, `domain/` | `services/`, `api/`, `infra/`, `workers/` |
| `classifier/` | `domain/` | `api/`, `services/`, `repositories/`, `workers/` |
| `workers/` | `services/`, `infra/`, `classifier/` | `api/` |
| `domain/` | stdlib only | everything else |
| `db/` | `domain/`, SQLAlchemy | `services/`, `api/` |
| `infra/` | `domain/` | `api/`, `services/`, `repositories/` |

---

## Data Flow

### Ingestion Flow

```
Atmoz SFTP
    │  poll every N seconds
    ▼
ingestion_worker.py
    │  1. detect stable file (size + mtime unchanged across 2 polls)
    │  2. validate TIFF magic bytes
    │  3. compute SHA-256 checksum
    │  4. check duplicate in Postgres
    ▼
IngestionService
    │  5. create Batch + Document records (status=pending)
    │  6. upload original TIFF → MinIO originals bucket
    │  7. mark document stored
    │  8. enqueue RQ job (document_id + model_metadata_id only)
    │  9. create ClassificationJob record (status=queued)
    │  10. mark document queued
    │  11. audit event
    │  12. commit → invalidate batch-list cache
    ▼
Redis Queue (RQ)
```

### Inference Flow

```
Redis Queue (RQ)
    │  consume job
    ▼
inference_worker.py
    │  1. startup: validate classifier.pt + model_card.json
    │  2. fetch document + TIFF from MinIO
    │  3. validate TIFF readability
    │  4. preprocess → tensor
    │  5. ConvNeXt forward pass → logits
    │  6. map logits → RVL-CDIP 16-class scores + top-1
    ▼
ClassificationJobService
    │  7. persist Prediction (predicted_class, confidence, scores, review_eligible)
    │  8. generate overlay PNG → MinIO overlays bucket
    │  9. persist OverlayAsset
    │  10. mark ClassificationJob succeeded
    │  11. audit event
    │  12. commit → invalidate batch + prediction caches
```

### API Review Flow

```
Reviewer (JWT)
    │  GET /predictions/{id}  → read prediction + overlay URL
    │  POST /predictions/{id}/review  → submit relabel
    ▼
PredictionReviewService
    │  1. check review_eligible (confidence < 0.7)
    │  2. validate label against RVL-CDIP classes
    │  3. set review_label + reviewed_by + reviewed_at
    │  4. audit event
    │  5. commit → invalidate prediction + batch + audit caches
```

---

## Storage

| Store | Purpose | Technology |
|---|---|---|
| Postgres 16 | All relational data, audit events, job state | SQLAlchemy 2.x ORM + Alembic |
| MinIO | Original TIFFs, annotated overlay PNGs | MinIO Python client |
| Redis 7 | RQ job queue + fastapi-cache2 response cache | redis-py |
| Vault (dev) | JWT secret, SFTP creds, MinIO creds, DB creds | hvac |

---

## Authentication and Authorization

- **Authentication**: fastapi-users with JWT. Login returns a bearer token.
- **Authorization**: Casbin SQLAlchemy adapter with RBAC policy model.
  Policy checks happen in services, not in routers.
- **Roles**: `admin`, `reviewer`, `auditor` — see [DECISIONS.md](DECISIONS.md)
  for role matrix.

---

## Cache Strategy

fastapi-cache2 with Redis backend. Cache keys include role context where
authorization changes the visible data. Invalidation happens in services
after a successful commit — never in routers or repositories.

| Event | Invalidated keys |
|---|---|
| Document ingested | `batches:list:{role}` |
| Classification complete | `batches:list`, `batches:detail:{id}`, `predictions:detail:{id}` |
| Prediction relabeled | same as above + `audit:list:{role}` |
| Role changed | `users:roles:{user_id}` + all role-scoped batch keys |

---

## Why the API Does Not Run Inference

Inference requires loading a ~100 MB PyTorch model into memory, GPU/CPU
compute, and preprocessing dependencies (torchvision, Pillow). Mixing this
into the API process would:

- Increase API startup time and memory footprint
- Make the API pod unscalable independently of inference load
- Violate the single-responsibility principle for the HTTP layer

The inference worker is a separate process that owns the classifier runtime
entirely. The API only reads prediction results from Postgres.
