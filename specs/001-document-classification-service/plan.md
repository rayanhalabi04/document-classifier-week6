# Implementation Plan: Internal Document Classification Service

**Branch**: `001-document-classification-service` | **Date**: 2026-05-11 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/001-document-classification-service/spec.md`

**Note**: This plan is produced for implementation planning only. Do not implement application code in this phase.

## Summary

Build a local Docker Compose internal document classification service. A scanner vendor drops grayscale TIFF files into Atmoz SFTP. An ingestion worker detects stable files, uploads originals to MinIO, records document state in Postgres 16, and enqueues Redis Queue jobs through Redis 7. An inference worker loads a torchvision ConvNeXt Tiny or Small classifier from `classifier.pt`, validates `model_card.json`, classifies documents into one RVL-CDIP 16 layout class, writes predictions to Postgres, writes annotated overlay PNGs to MinIO, and invalidates affected fastapi-cache2 Redis cache entries. The FastAPI API uses fastapi-users with JWT authentication and Casbin SQLAlchemy adapter authorization; it exposes only user, role, batch, prediction review, and audit workflows. The API must not run inference.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Alembic, fastapi-users with JWT, Casbin SQLAlchemy adapter, fastapi-cache2 Redis backend, Redis Queue, MinIO Python client, Paramiko-compatible SFTP access, HashiCorp Vault client, PyTorch, torchvision ConvNeXt Tiny or Small  
**Storage**: Postgres 16 for relational data and audit events; MinIO for original TIFFs and overlay PNGs; Redis 7 for RQ and cache; Vault dev mode KV v2 for local secrets  
**Testing**: pytest, pytest-asyncio, HTTP contract tests, repository tests against Postgres, service tests, worker integration tests, golden-set replay tests  
**Target Platform**: Local Docker Compose environment plus GitHub Actions CI  
**Project Type**: Backend API with ingestion and inference worker processes  
**Performance Goals**: Valid TIFF visible with prediction and overlay within 2 minutes locally; reviewer relabel under 60 seconds after opening detail; CI golden-set replay completes within the CI budget  
**Constraints**: API never performs inference; reviewer relabel only when top-1 confidence is below 0.7; originals must be stored before queueing; service layer owns transactions and cache invalidation; repositories own SQL only  
**Scale/Scope**: Week 6 internal demonstration with local services, representative document batches, authenticated user workflows, auditability, and repeatable onboarding

## Folder Structure

```text
app/
├── main.py
├── api/
│   ├── __init__.py
│   ├── auth.py
│   ├── users.py
│   ├── roles.py
│   ├── batches.py
│   ├── predictions.py
│   ├── audit.py
│   └── health.py
├── services/
│   ├── ingestion.py
│   ├── classification_jobs.py
│   ├── prediction_review.py
│   ├── role_management.py
│   ├── audit_log.py
│   ├── startup_validation.py
│   └── cache_invalidation.py
├── repositories/
│   ├── users.py
│   ├── roles.py
│   ├── batches.py
│   ├── documents.py
│   ├── jobs.py
│   ├── predictions.py
│   ├── model_metadata.py
│   └── audit_events.py
├── domain/
│   ├── roles.py
│   ├── batches.py
│   ├── documents.py
│   ├── predictions.py
│   ├── jobs.py
│   ├── audit.py
│   └── model_metadata.py
├── infra/
│   ├── db.py
│   ├── redis.py
│   ├── queue.py
│   ├── cache.py
│   ├── minio.py
│   ├── sftp.py
│   ├── vault.py
│   └── casbin.py
├── db/
│   ├── models.py
│   └── session.py
├── workers/
│   ├── ingestion_worker.py
│   └── inference_worker.py
└── classifier/
    ├── loader.py
    ├── validation.py
    ├── preprocessing.py
    ├── inference.py
    ├── overlays.py
    └── golden_replay.py

alembic/
tests/
├── unit/
├── repository/
├── service/
├── contract/
├── integration/
└── golden/

.github/workflows/ci.yml
docker-compose.yml
classifier.pt
model_card.json
ARCH.md
DECISIONS.md
RUNBOOK.md
SECURITY.md
COLLABORATION.md
```

## API Endpoints

Authentication uses fastapi-users JWT. Authorization decisions use Casbin policy checks in services or dependencies, not inline business logic in routers.

| Method | Path | Roles | Purpose |
|--------|------|-------|---------|
| `POST` | `/auth/jwt/login` | Public | Sign in and receive JWT |
| `POST` | `/auth/jwt/logout` | Authenticated | Logout or revoke active session semantics where supported |
| `GET` | `/users/me` | Authenticated | Read current user profile and roles |
| `POST` | `/users/invitations` | admin | Invite an internal user |
| `GET` | `/users` | admin | List users for role administration |
| `PUT` | `/users/{user_id}/roles` | admin | Replace or toggle user roles |
| `GET` | `/batches` | admin, reviewer, auditor | List batches with status and review counts |
| `GET` | `/batches/{batch_id}` | admin, reviewer, auditor | Read batch detail and document summaries |
| `GET` | `/predictions/{prediction_id}` | admin, reviewer, auditor | Read prediction, confidence, overlay URL, and review status |
| `POST` | `/predictions/{prediction_id}/review` | reviewer | Relabel prediction when top-1 confidence is below 0.7 |
| `GET` | `/audit-events` | admin, auditor | List audit events with filters |
| `GET` | `/health/live` | Public | Liveness check |
| `GET` | `/health/ready` | Public | Readiness check for dependencies and startup validation |

The API intentionally has no endpoint for running inference, uploading scanner documents, or directly enqueueing arbitrary classification jobs.

## Database Tables

All tables are managed by Alembic migrations and SQLAlchemy 2.x ORM models in `app/db/models.py`.

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `users` | fastapi-users compatible internal users | `id`, `email`, `hashed_password`, `is_active`, `is_verified`, `created_at`, `updated_at`, `last_login_at` |
| `role_assignments` | Active and historical role grants | `id`, `user_id`, `role`, `assigned_by_user_id`, `assigned_at`, `revoked_at` |
| `casbin_rule` | Casbin SQLAlchemy adapter policy storage | `id`, `ptype`, `v0`, `v1`, `v2`, `v3`, `v4`, `v5` |
| `batches` | Vendor ingestion grouping | `id`, `source`, `status`, `document_count`, `reviewable_count`, `created_at`, `updated_at`, `completed_at` |
| `documents` | Source TIFF metadata and original object location | `id`, `batch_id`, `source_path`, `source_filename`, `source_size_bytes`, `source_checksum`, `blob_bucket`, `blob_key`, `mime_type`, `ingestion_status`, `failure_reason`, `created_at`, `updated_at` |
| `classification_jobs` | Durable view of RQ job lifecycle | `id`, `document_id`, `rq_job_id`, `status`, `attempt_count`, `last_error`, `enqueued_at`, `started_at`, `finished_at` |
| `model_metadata` | Loaded classifier identity and label contract | `id`, `model_name`, `model_architecture`, `model_version`, `labels_json`, `model_card_sha256`, `classifier_sha256`, `created_at` |
| `predictions` | Model output and review state | `id`, `document_id`, `model_metadata_id`, `predicted_class`, `top1_confidence`, `class_scores_json`, `review_eligible`, `review_label`, `reviewed_by_user_id`, `reviewed_at`, `created_at`, `updated_at` |
| `overlay_assets` | Annotated PNG object location | `id`, `prediction_id`, `blob_bucket`, `blob_key`, `content_type`, `created_at` |
| `audit_events` | Immutable operational and security events | `id`, `actor_user_id`, `action`, `target_type`, `target_id`, `outcome`, `details_json`, `request_id`, `created_at` |

Important constraints:

- `documents.source_checksum` plus source identity prevents duplicate active ingestion.
- `predictions.document_id` has one active prediction per document version.
- `predictions.review_eligible` is derived from `top1_confidence < 0.7`.
- `review_label` must be one of the RVL-CDIP 16 classes.
- audit rows are append-only; no update path except migrations.

## Worker Flow

### Ingestion Worker

1. Connect to Atmoz SFTP using credentials retrieved from Vault dev mode KV v2.
2. Poll the configured vendor drop directory.
3. Detect file stability by comparing size and modified timestamp across polling intervals.
4. Reject unsupported files; record failed document or audit event for corrupted, unreadable, non-TIFF, or partial files.
5. Compute checksum and check duplicate identity in Postgres.
6. Create or update a batch and document record in a service transaction.
7. Upload the original TIFF to MinIO.
8. Mark document as `stored`.
9. Enqueue an RQ job with only the document identifier and model metadata identifier.
10. Mark document as `queued`, create `classification_jobs` record, audit the enqueue outcome, and invalidate affected batch-list caches.

### Inference Worker

1. On worker startup, run classifier startup validation.
2. Consume RQ jobs from Redis 7.
3. Load document metadata and original TIFF from MinIO.
4. Validate image readability and expected grayscale TIFF constraints.
5. Preprocess image for torchvision ConvNeXt Tiny or Small.
6. Run inference and map logits to the RVL-CDIP 16-class label list from `model_card.json`.
7. Persist prediction with class scores, top-1 confidence, review eligibility, model metadata, and status updates in one service transaction.
8. Generate annotated overlay PNG and store it in MinIO.
9. Record overlay asset location.
10. Mark job succeeded or failed with retryable/terminal state.
11. Audit classification outcome.
12. Invalidate batch, prediction, review queue, and audit caches affected by the document.

## Cache Invalidation Strategy

Use fastapi-cache2 with Redis backend for read-mostly API responses. Cache keys must include user role context where authorization affects visible data.

| Cached View | Example Key Scope | Invalidate When |
|-------------|-------------------|-----------------|
| Batch list | `batches:list:{role_hash}:{filters}` | batch created, document added, classification status changes, relabel changes review counts |
| Batch detail | `batches:detail:{batch_id}:{role_hash}` | document status changes, prediction created, overlay created, relabel submitted |
| Prediction detail | `predictions:detail:{prediction_id}:{role_hash}` | prediction created, overlay created, relabel submitted |
| Audit list | `audit:list:{role_hash}:{filters}` | audit event inserted |
| User role view | `users:roles:{user_id}` | admin changes role assignments |

Rules:

- Services call `cache_invalidation.py`; routers never invalidate directly.
- Repository methods never read or write cache.
- Any transaction that changes persisted data publishes invalidation only after successful commit.
- If Redis cache deletion fails, the service logs and audits the failure where appropriate, but persisted Postgres data remains authoritative.
- Role changes invalidate user-role cache and all role-scoped API cache keys for the affected user.

## Startup Validation Rules

API and workers must fail fast in readiness checks when required local dependencies or assets are invalid.

API startup/readiness:

- Postgres 16 connection succeeds and Alembic head migration is applied.
- Redis 7 connection succeeds.
- MinIO buckets for originals and overlays exist or can be created by startup bootstrap.
- Vault dev mode KV v2 path is reachable and required secrets exist.
- Casbin policy storage is reachable and baseline policies for `admin`, `reviewer`, and `auditor` are loaded.
- fastapi-users JWT secret is present and not a placeholder.
- cache backend initializes against Redis.

Ingestion worker startup:

- SFTP connection succeeds against Atmoz SFTP.
- Vendor drop directory exists and is readable.
- MinIO original bucket is writable.
- Redis Queue enqueue path is available.

Inference worker startup:

- `classifier.pt` exists and checksum matches `model_card.json`.
- `model_card.json` parses successfully and contains exactly 16 RVL-CDIP labels.
- model architecture is `convnext_tiny` or `convnext_small`.
- preprocessing settings match the model card.
- a dry-run tensor validation confirms output dimension equals 16.
- MinIO original bucket is readable and overlay bucket is writable.
- Postgres and Redis Queue connections are available.

## Tests

Unit tests:

- domain validation for roles, RVL-CDIP labels, review eligibility, and state transitions
- classifier model-card parsing and label mapping
- cache key generation and invalidation target selection
- startup validation failure cases

Repository tests:

- SQLAlchemy 2.x CRUD and query behavior for each table
- duplicate document detection by checksum and source identity
- append-only audit event behavior
- Alembic migration upgrade from empty database

Service tests:

- ingestion transaction creates batch/document/job only after object storage success
- classification persistence preserves original model prediction
- relabel rejects predictions at or above 0.7 confidence
- role-management enforces admin-only changes
- cache invalidation runs after commit

API contract tests:

- OpenAPI schema generated and matches planned routes
- JWT-protected routes reject anonymous access
- admin, reviewer, and auditor permissions match the role matrix
- API has no inference endpoint

Integration tests:

- docker-compose dependency health checks
- Atmoz SFTP drop to MinIO original upload and RQ enqueue
- RQ inference job to Postgres prediction and MinIO overlay
- audit events for denied writes and successful relabels
- fastapi-cache2 Redis cache invalidates after relabel and classification

Golden tests:

- golden-set replay loads `classifier.pt` and `model_card.json`
- preprocessing and label mapping produce expected classes for fixtures
- CI reports deterministic pass/fail output

## CI Stages

GitHub Actions workflow stages:

1. **Lint and format check**: ruff or equivalent linting, import ordering, formatting check.
2. **Type and static checks**: run type checks where configured and validate no forbidden imports violate architecture ownership.
3. **Unit tests**: run fast tests without Docker services.
4. **Database migration check**: start Postgres 16 service, run Alembic upgrade, verify metadata tables.
5. **Contract tests**: validate OpenAPI generation and endpoint authorization matrix.
6. **Integration tests**: start Redis 7, Postgres 16, MinIO, Vault dev mode, and Atmoz SFTP services for worker/API integration tests.
7. **Golden-set replay**: run classifier fixture replay with ConvNeXt Tiny or Small assets.
8. **Docker Compose smoke test**: build images, start stack, call `/health/live` and `/health/ready`.
9. **Documentation check**: verify `ARCH.md`, `DECISIONS.md`, `RUNBOOK.md`, `SECURITY.md`, and `COLLABORATION.md` exist and mention required local workflows.

## Docker Compose Services

Planned services:

- `api`: FastAPI app
- `ingestion-worker`: SFTP polling and enqueue worker
- `inference-worker`: RQ worker with classifier runtime
- `postgres`: Postgres 16
- `redis`: Redis 7
- `minio`: object storage for originals and overlays
- `vault`: HashiCorp Vault dev mode with KV v2 mounted
- `sftp`: Atmoz SFTP vendor drop simulation

Compose volumes:

- Postgres data
- Redis data where useful for local debugging
- MinIO data
- Vault dev data or bootstrap scripts
- SFTP drop folder
- classifier assets mounted read-only into inference worker

## Trello Ownership Suggestions

Use four member lanes or labels, with shared review on cross-cutting cards.

| Member | Suggested Ownership | Example Cards |
|--------|---------------------|---------------|
| Member 1: API/Auth/RBAC | FastAPI routers, fastapi-users JWT, Casbin policies, role matrix, API contract tests | auth endpoints, user invitation, role toggling, permission denial tests |
| Member 2: Data/Persistence/Audit | SQLAlchemy models, Alembic migrations, repositories, audit event persistence | tables, migrations, repository tests, audit log queries |
| Member 3: Ingestion/Infra/Compose | Docker Compose, Postgres/Redis/MinIO/Vault/SFTP wiring, ingestion worker, MinIO uploads, RQ enqueue | compose stack, Vault secrets, SFTP polling, duplicate detection |
| Member 4: Classifier/Worker/CI | ConvNeXt loader, preprocessing, inference worker, overlay generation, golden-set replay, GitHub Actions | classifier validation, RQ consumer, overlay PNGs, CI stages |

Shared cards:

- Architecture boundary checks
- RUNBOOK and SECURITY documentation
- End-to-end smoke test
- Cache invalidation acceptance tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution file currently contains placeholder principles and no enforceable project-specific gates. This plan applies the explicit gates from the feature specification:

- PASS: API layer remains HTTP-router only and does not perform inference.
- PASS: Business logic, transactions, and cache invalidation are owned by services.
- PASS: Repositories own SQL access only.
- PASS: Domain models stay in `app/domain`.
- PASS: Infrastructure adapters stay in `app/infra`.
- PASS: SQLAlchemy ORM models stay in `app/db/models.py`.
- PASS: Classifier loading, validation, preprocessing, inference, and golden-set replay stay in `app/classifier`.
- PASS: Persistent data has Alembic migration coverage.
- PASS: Authentication, authorization, audit logging, and role-based access are first-class requirements.
- PASS: Local Docker Compose operation and documentation deliverables are required outcomes.

Post-design check: PASS. The plan, data model, contract, and quickstart preserve the same boundaries and do not introduce conflicting components.

## Complexity Tracking

No constitution violations or unresolved complexity exceptions are present.
