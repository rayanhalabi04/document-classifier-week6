# Research: Internal Document Classification Service

## Decision: Use FastAPI only as the authenticated HTTP boundary

**Rationale**: The API must expose authentication, authorization, batch listing, prediction review, audit access, and role management while keeping inference outside the request path. FastAPI is a required deliverable and fits a local service API with generated OpenAPI contracts.

**Alternatives considered**: Running inference from API handlers was rejected because the specification forbids it and it would couple user latency to model execution. A CLI-only interface was rejected because authenticated user workflows are required.

## Decision: Use Redis Queue for asynchronous classification jobs

**Rationale**: Redis Queue is a required deliverable and provides a simple local worker model. Ingestion can enqueue work after original storage succeeds, while inference workers can retry or fail jobs without blocking the API.

**Alternatives considered**: Direct synchronous classification was rejected because it violates the API and ingestion separation. A heavier workflow orchestrator was rejected as unnecessary for the Week 6 local scope.

## Decision: Store originals and overlays in MinIO

**Rationale**: TIFF originals and annotated overlay PNGs are binary assets that should not live in relational tables. MinIO is a required local object-store deliverable and mirrors production-style blob storage while remaining docker-compose friendly.

**Alternatives considered**: Filesystem-only storage was rejected because it weakens local service parity and makes metadata, retry, and cleanup rules less explicit. Database BLOBs were rejected because prediction and audit queries should remain relational and lightweight.

## Decision: Use Postgres as the source of truth for users, batches, documents, jobs, predictions, role assignments, and audit events

**Rationale**: These records require relationships, transactional updates, migrations, and auditability. Postgres and Alembic are required deliverables, and repository ownership keeps SQL isolated.

**Alternatives considered**: Redis as primary storage was rejected because queue/cache state is not the durable record of business activity. Object metadata embedded only in MinIO was rejected because it does not support review and audit workflows well.

## Decision: Apply Casbin for authorization policy and fastapi-users for authentication

**Rationale**: Both are required deliverables. Authentication identifies users through fastapi-users JWT flows; authorization checks role capabilities for admin, reviewer, and auditor operations through Casbin policy backed by the SQLAlchemy adapter. This keeps role policy explicit and testable.

**Alternatives considered**: Hard-coded role checks in routers were rejected because routers must remain thin and policy behavior needs centralized tests. Anonymous internal access was rejected because all user workflows require accountability.

## Decision: Use torchvision ConvNeXt Tiny or Small for visual document inference

**Rationale**: The requested classifier family is available through torchvision and is appropriate for image classification with a fixed 16-class output head. Startup validation must verify that `classifier.pt`, `model_card.json`, preprocessing settings, architecture name, checksum, and label list are consistent before workers accept jobs.

**Alternatives considered**: Training a new model was rejected because the specification requires a pretrained classifier asset. Running a larger model by default was rejected because the local Docker Compose scope should favor predictable resource use.

## Decision: Cache only derived read views and invalidate from services

**Rationale**: Batch lists and prediction views are good cache candidates, but persisted records must remain authoritative. The spec requires services to own cache invalidation after ingestion, classification, relabeling, and role changes.

**Alternatives considered**: Caching inside repositories was rejected because repositories own SQL only. Caching inside routers was rejected because routers should not own business behavior.

## Decision: Represent duplicate detection with source identity and checksum

**Rationale**: Scanner feeds can resend files. Tracking source path/name, observed timestamp, size, and checksum supports idempotent ingestion and prevents duplicate active predictions unless a new version is explicitly recorded.

**Alternatives considered**: Filename-only detection was rejected because vendors can resend changed content with the same name. Checksum-only detection was rejected because source traceability matters for audit and operations.

## Decision: Make the golden-set replay a CI verification target

**Rationale**: The classifier is pretrained, so project confidence comes from deterministic validation of preprocessing, model loading, label mapping, and expected outputs against a known fixture set.

**Alternatives considered**: Training-time metrics were rejected because training is out of scope. Manual visual inspection was rejected because it is not repeatable enough for CI.

## Decision: Use explicit operational states for documents, jobs, and predictions

**Rationale**: Ingestion and inference involve multiple services and failure points. Explicit states make retries, terminal failures, review eligibility, and operator diagnosis testable.

**Alternatives considered**: A single free-text status field was rejected because it would make behavior ambiguous. Hiding failures from users was rejected because operators need to diagnose local service issues.
