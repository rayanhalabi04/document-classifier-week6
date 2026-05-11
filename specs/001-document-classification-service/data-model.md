# Data Model: Internal Document Classification Service

## Database Tables

The planned SQLAlchemy 2.x and Alembic schema contains:

- `users`
- `role_assignments`
- `casbin_rule`
- `batches`
- `documents`
- `classification_jobs`
- `model_metadata`
- `predictions`
- `overlay_assets`
- `audit_events`

## User

Represents an authenticated internal account.

**Fields**: `id`, `email`, `display_name`, `is_active`, `is_verified`, `invited_by_user_id`, `invited_at`, `created_at`, `updated_at`, `last_login_at`

**Relationships**: Has many role assignments; can author audit events, invitations, and relabel actions.

**Validation Rules**: Email must be unique; inactive users cannot perform protected actions; role changes require admin authorization.

## Role Assignment

Represents a user's permissions.

**Fields**: `id`, `user_id`, `role`, `assigned_by_user_id`, `assigned_at`, `revoked_at`

**Relationships**: Belongs to a user and an assigning admin.

**Validation Rules**: Role must be one of `admin`, `reviewer`, or `auditor`; active duplicate role assignments are not allowed.

## Batch

Represents a group of documents ingested from vendor drop activity.

**Fields**: `id`, `source`, `status`, `document_count`, `created_at`, `updated_at`, `completed_at`

**Relationships**: Has many documents and predictions through documents.

**State Transitions**: `open` -> `processing` -> `completed`; `open` or `processing` -> `failed` when unrecoverable batch-level failure occurs.

## Document

Represents a source grayscale TIFF document image.

**Fields**: `id`, `batch_id`, `source_path`, `source_filename`, `source_size_bytes`, `source_checksum`, `blob_uri`, `mime_type`, `ingestion_status`, `failure_reason`, `created_at`, `updated_at`

**Relationships**: Belongs to a batch; has one or more classification jobs over time; has at most one active prediction.

**Validation Rules**: Accepted documents must be TIFF files; source checksum and source identity drive duplicate detection; original blob URI must exist before a classification job is queued.

**State Transitions**: `detected` -> `stabilizing` -> `stored` -> `queued` -> `classified`; any pre-classified state may move to `failed` with a reason.

## Classification Job

Represents asynchronous inference work for a document.

**Fields**: `id`, `document_id`, `queue_job_id`, `status`, `attempt_count`, `last_error`, `enqueued_at`, `started_at`, `finished_at`

**Relationships**: Belongs to one document; creates or updates one prediction when successful.

**Validation Rules**: A document must not have multiple active in-progress jobs for the same document version; retries must be idempotent.

**State Transitions**: `queued` -> `running` -> `succeeded`; `queued` or `running` -> `retryable_failed`; `retryable_failed` -> `queued`; any non-terminal state -> `terminal_failed` after retry exhaustion or unrecoverable input failure.

## Prediction

Represents classifier output and optional human correction.

**Fields**: `id`, `document_id`, `model_name`, `model_version`, `predicted_class`, `top1_confidence`, `class_scores`, `review_eligible`, `review_label`, `reviewed_by_user_id`, `reviewed_at`, `overlay_uri`, `created_at`, `updated_at`

**Relationships**: Belongs to a document; may reference a reviewer user; has audit events for review actions.

**Validation Rules**: Predicted class and review label must be in the RVL-CDIP 16-class taxonomy; `review_eligible` is true only when top-1 confidence is below 0.7; reviewer relabel is allowed only when `review_eligible` is true.

## Overlay Asset

Represents the annotated PNG stored for review.

**Fields**: `id`, `prediction_id`, `blob_uri`, `content_type`, `created_at`

**Relationships**: Belongs to one prediction.

**Validation Rules**: Content type must be PNG; asset must correspond to the same document and prediction it annotates.

## Audit Event

Represents an immutable accountability record.

**Fields**: `id`, `actor_user_id`, `action`, `target_type`, `target_id`, `outcome`, `details`, `created_at`, `request_id`

**Relationships**: Optionally belongs to an actor user; references target records by type and identifier.

**Validation Rules**: Audit events are append-only; security-sensitive events must include action, target, outcome, and timestamp.

## Model Metadata

Represents the model identity and label contract used for prediction interpretation.

**Fields**: `id`, `model_name`, `model_version`, `labels`, `model_card_uri`, `classifier_asset_uri`, `created_at`

**Relationships**: Referenced by predictions.

**Validation Rules**: Labels must contain exactly the RVL-CDIP 16 layout classes; model metadata must match the loaded classifier asset before inference starts.
