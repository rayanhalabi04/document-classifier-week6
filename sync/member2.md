# Member 2 — Services / Repositories / Database

## Done

### T015 — SQLAlchemy 2.x ORM Schema (`app/db/models.py`)

All 10 tables implemented with SQLAlchemy 2.x `Mapped` / `mapped_column` style.
3 PostgreSQL native ENUM types defined.

#### Database Schema

| Table | Key Columns | Notes |
|---|---|---|
| `users` | `id` UUID PK, `email` UNIQUE, `hashed_password`, `is_active`, `is_verified`, `is_superuser`, `created_at`, `updated_at`, `last_login_at` | Extends fastapi-users base |
| `role_assignments` | `id` UUID PK, `user_id` FK→users, `role`, `assigned_by_user_id` FK→users, `assigned_at`, `revoked_at` | Partial index prevents duplicate active roles |
| `casbin_rule` | `id` INT PK, `ptype`, `v0`–`v5` | Casbin SQLAlchemy adapter compatible |
| `batches` | `id` UUID PK, `source`, `status` ENUM, `document_count`, `reviewable_count`, `created_at`, `updated_at`, `completed_at` | Indexed on `status`, `created_at` |
| `documents` | `id` UUID PK, `batch_id` FK→batches, `source_path`, `source_filename`, `source_size_bytes`, `source_checksum`, `blob_bucket`, `blob_key`, `mime_type`, `ingestion_status` ENUM, `failure_reason`, `created_at`, `updated_at` | Partial index blocks duplicate active ingestion |
| `classification_jobs` | `id` UUID PK, `document_id` FK→documents, `rq_job_id`, `status` ENUM, `attempt_count`, `last_error`, `enqueued_at`, `started_at`, `finished_at` | Tracks full RQ job lifecycle |
| `model_metadata` | `id` UUID PK, `model_name`, `model_architecture`, `model_version`, `labels_json` JSONB, `model_card_sha256`, `classifier_sha256`, `created_at` | Classifier identity + label contract |
| `predictions` | `id` UUID PK, `document_id` FK→documents, `model_metadata_id` FK→model_metadata, `predicted_class`, `top1_confidence`, `class_scores_json` JSONB, `review_eligible`, `review_label`, `reviewed_by_user_id` FK→users, `reviewed_at`, `created_at`, `updated_at` | `review_eligible` = confidence < 0.7 |
| `overlay_assets` | `id` UUID PK, `prediction_id` FK→predictions, `blob_bucket`, `blob_key`, `content_type`, `created_at` | Annotated PNG location in MinIO |
| `audit_events` | `id` UUID PK, `actor_user_id` UUID (no FK), `action`, `target_type`, `target_id`, `outcome`, `details_json` JSONB, `request_id`, `created_at` | Append-only, no FK on actor to survive user deletion |

#### ENUM Types

| Type | Values |
|---|---|
| `batchstatus` | `pending`, `processing`, `completed`, `failed` |
| `ingestionstatus` | `pending`, `stored`, `queued`, `processing`, `completed`, `failed` |
| `jobstatus` | `queued`, `running`, `succeeded`, `retryable_failed`, `terminal_failed` |

#### Table Relationships

```
users ──────────────── role_assignments   (one user → many roles)
users ──────────────── predictions        (reviewer → relabeled predictions)
batches ────────────── documents          (one batch → many documents)
documents ──────────── classification_jobs
documents ──────────── predictions
predictions ─────────── overlay_assets
model_metadata ──────── predictions
audit_events            (standalone — no FK)
casbin_rule             (standalone — managed by Casbin)
```

---

### T016 — Alembic Migration (`alembic/versions/001_initial_schema.py`)

- `backend/alembic.ini` — Alembic config, DB URL read from `DATABASE_URL` env var
- `backend/alembic/env.py` — connects Alembic to `Base.metadata`, reads env var
- `backend/alembic/script.py.mako` — migration file template
- `backend/alembic/versions/001_initial_schema.py` — creates all 10 tables, 3 ENUM types, all indexes in correct FK dependency order
- `downgrade()` drops tables in reverse order then drops ENUMs

Run: `alembic upgrade head` → creates all tables in a fresh Postgres 16 DB

---

### T017 — Repository Interfaces — Core Entities

All repositories use SQLAlchemy 2.x `select()`. SQL only — no business logic, no cache, no transactions.

| File | Class | Key Methods |
|---|---|---|
| `app/repositories/batches.py` | `BatchRepository` | `get_by_id`, `list(status, limit, offset)`, `create`, `update` |
| `app/repositories/documents.py` | `DocumentRepository` | `get_by_id`, `list_by_batch`, `find_active_duplicate`, `create`, `update` |
| `app/repositories/jobs.py` | `ClassificationJobRepository` | `get_by_id`, `get_by_rq_job_id`, `list_by_document`, `get_active_by_document`, `create`, `update` |
| `app/repositories/predictions.py` | `PredictionRepository` | `get_by_id`, `get_by_document_id`, `list_review_eligible`, `create`, `update`, `create_overlay`, `get_overlay_by_prediction` |
| `app/repositories/audit_events.py` | `AuditEventRepository` | `create`, `get_by_id`, `list(actor_user_id, action, target_type, target_id, limit, offset)` |

---

### T018 — User and Role Repositories

| File | Class | Key Methods |
|---|---|---|
| `app/repositories/users.py` | `UserRepository` | `get_by_id`, `get_by_email`, `list`, `update` |
| `app/repositories/roles.py` | `RoleRepository` | `get_active_roles`, `has_active_role`, `get_by_id`, `create`, `revoke`, `revoke_all_for_user` |
| `app/repositories/model_metadata.py` | `ModelMetadataRepository` | `get_by_id`, `get_latest`, `get_by_classifier_checksum`, `create` |

---

### T019 — Ingestion Service (`app/services/ingestion.py`)

- `IngestionService.ingest_file()` — full pipeline: validate TIFF magic bytes → checksum → duplicate check → create Batch+Document → upload to MinIO → enqueue RQ → create ClassificationJob → audit → commit → invalidate cache
- `IngestionService.mark_failed()` — records failed ingestion attempt as audit event
- Transaction boundary: service owns `commit()` — upload must succeed before queue

---

### T020 — Classification Job Service (`app/services/classification_jobs.py`)

- `mark_running(job_id)` — queued → running
- `persist_result(...)` — saves Prediction + OverlayAsset + job succeeded in one transaction
- `mark_retryable_failure(job_id, error)` — retryable failure state
- `mark_terminal_failure(job_id, error)` — terminal failure state
- All state changes are audited

---

### T021 — Prediction Review Service (`app/services/prediction_review.py`)

- `relabel(prediction_id, review_label, reviewer_user_id, batch_id)` — applies reviewer label
- Rejects `top1_confidence >= 0.7` with `ReviewNotEligible`
- Validates label against all 16 RVL-CDIP classes
- Original `predicted_class` and `top1_confidence` are never modified
- Audits every relabel and invalidates prediction + batch + audit caches

---

### T022 — Audit Log Service (`app/services/audit_log.py`)

- `AuditLogService.record(action, outcome, actor_user_id, target_type, target_id, details, request_id)`
- Flush only — caller owns commit
- Used by all other services — never called from routers directly

---

### T023 — Startup Validation Service (`app/services/startup_validation.py`)

Three separate check sets:
- `run_api_readiness_checks()` — Postgres + Alembic head, Redis, MinIO buckets, Vault, Casbin baseline policies, JWT secret
- `run_ingestion_worker_checks()` — SFTP, MinIO originals writable, RQ available
- `run_inference_worker_checks()` — classifier assets, MinIO, RQ, Redis

Each check raises `StartupValidationError` on failure with a safe message (no credentials or stack traces).

---

### T034 — Cache Invalidation (`app/services/cache_invalidation.py`)

- `invalidate_batch_list()` — clears batch list for all roles
- `invalidate_batch_detail(batch_id)` — clears batch detail for all roles
- `invalidate_prediction_detail(prediction_id)` — clears prediction detail for all roles
- `invalidate_audit_list()` — clears audit list for all roles
- `invalidate_user_roles(user_id)` — clears user role cache + all role-scoped keys
- `invalidate_after_classification(batch_id, prediction_id)` — composite
- `invalidate_after_relabel(batch_id, prediction_id)` — composite
- Redis failure is logged but never rolls back Postgres data

---

### T060 — Domain Errors (`app/domain/errors.py`)

Typed error hierarchy — no bare `except` anywhere:

```
AppError
├── DuplicateDocumentError
├── UnsupportedFileTypeError
├── StorageError
├── SFTPError
├── ClassificationError
├── ModelValidationError
├── PredictionNotFound
├── ReviewNotEligible
├── InvalidReviewLabel
├── PermissionDenied
├── StartupValidationError
└── CacheInvalidationError
```

---

### T061 — Structured Logging (`app/infra/logging.py`)

- `configure_logging()` — structlog with JSON (production) or console (dev) renderer
- `set_request_id(request_id)` — binds request ID to all logs in the API request context
- `set_job_id(job_id)` — binds job ID to all logs in a worker job context
- `get_logger(name)` — returns a bound structlog logger
- Every log line automatically includes `request_id` and `job_id` from context vars
- Never logs passwords, tokens, secrets, or raw stack traces

---

### Role Management Service (`app/services/role_management.py`)

- `assign_role(target, role, admin)` — idempotent, no-op if already active
- `revoke_role(target, role, admin)` — revokes one specific active role
- `replace_roles(target, new_roles, admin)` — atomic revoke-all + assign-new in one commit
- `get_active_roles(user_id)` — returns list of role name strings
- Every change audited and cache invalidated

---

### DB Session (`app/db/session.py` + `app/infra/db.py`)

- `SessionFactory` — sync SQLAlchemy sessionmaker, `expire_on_commit=False`
- `get_session()` — FastAPI `Depends()` dependency, rolls back on exception, always closes
- Workers use `SessionFactory()` directly (no FastAPI dependency injection)

---

### `backend/pyproject.toml` — All Dependencies Pinned

All packages pinned for reproducible installs:
`fastapi`, `sqlalchemy 2.0.30`, `alembic`, `fastapi-users`, `casbin`, `fastapi-cache2`, `redis`, `rq`, `minio`, `paramiko`, `hvac`, `torch`, `torchvision`, `structlog` + dev tools (`black`, `isort`, `flake8`, `mypy`, `pytest`)

Install: `uv pip install -e ".[dev]"`

---

### Documentation

| File | Contents |
|---|---|
| `docs/ARCH.md` | Module boundary diagram, import rules, ingestion/inference/review flows, cache strategy, why API never runs inference |
| `docs/DECISIONS.md` | 11 ADRs — FastAPI, SQLAlchemy sync, Alembic, RQ, MinIO, Vault, Casbin + role matrix, fastapi-cache2, ConvNeXt, separate workers, append-only audit |
| `docs/COLLABORATION.md` | Team ownership, Trello board structure, 5 integration review checkpoints |
| `README.md` | Local setup, test commands, branch naming, commit style, Python standards |
| `CONTRIBUTING.md` | Branch naming, PR requirements, review rules, naming conventions, docstring standard, error handling rules, secret hygiene |

---

## Remaining

| Task | What | Status |
|---|---|---|
| T057 | Python naming + docstring standards in CONTRIBUTING.md | ✅ Done (included in CONTRIBUTING.md) |
| T053 | Integration review checkpoints | ✅ Done (included in COLLABORATION.md) |
| Repository tests | `tests/repository/` — CRUD, duplicate detection, all repos | ✅ Done (95 tests, all passing) |
| Service tests | `tests/service/` — ingestion, classification jobs, relabel, role management | ✅ Done (95 tests, all passing) |

---

## Available for Member 3

The following files Member 3 needs are fully implemented and pushed:

| Member 3 needs | File | Status |
|---|---|---|
| Ingestion service skeleton (T019) | `app/services/ingestion.py` | ✅ Ready |
| Document repository (T017) | `app/repositories/documents.py` | ✅ Ready |
| Startup validation (T023) | `app/services/startup_validation.py` | ✅ Ready |
| DB session factory | `app/db/session.py` | ✅ Ready |
| StorageError + SFTPError types | `app/domain/errors.py` | ✅ Ready |
