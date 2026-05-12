# Architecture Decision Log

---

## ADR-001: FastAPI as the HTTP Framework

**Decision**: Use FastAPI with uvicorn.

**Reasons**:
- Native Pydantic v2 schema validation and automatic OpenAPI generation
- Dependency injection via `Depends()` maps cleanly to session and auth scopes
- fastapi-users integrates directly for JWT auth and user management

**Trade-offs**: Async-first design requires care when mixing with synchronous
SQLAlchemy sessions; resolved by using sync sessions throughout and relying
on uvicorn's thread pool for blocking calls.

---

## ADR-002: SQLAlchemy 2.x with Synchronous Sessions

**Decision**: Use SQLAlchemy 2.x ORM with synchronous `Session` for all
database access (API and workers).

**Reasons**:
- RQ workers are synchronous by design — async sessions would require
  `asyncio.run()` wrappers in every job
- SQLAlchemy 2.x type-annotated `Mapped` columns eliminate most runtime
  surprises from implicit nullability
- `expire_on_commit=False` keeps ORM objects usable after commit in workers

**Trade-offs**: FastAPI routes lose the benefit of async I/O for DB queries.
Acceptable for a local demo service with low concurrency.

---

## ADR-003: Alembic for All Schema Migrations

**Decision**: Every schema change is an Alembic migration. No `create_all()`
in application code.

**Reasons**:
- Reproducible upgrades and downgrades across environments
- CI can verify that an empty database reaches head cleanly
- Prevents schema drift between developer machines

---

## ADR-004: Redis Queue (RQ) for Inference Jobs

**Decision**: Use RQ over Celery or other task queues.

**Reasons**:
- Minimal configuration — a single Redis connection is sufficient
- Job arguments are kept small (document_id + model_metadata_id only)
  to avoid serializing large payloads through Redis
- RQ's job lifecycle (queued → started → finished/failed) maps directly
  to `ClassificationJob.status`

**Trade-offs**: RQ does not support distributed brokers or priority queues
out of the box. Sufficient for a single-node local demo.

---

## ADR-005: MinIO for Object Storage

**Decision**: Use MinIO for original TIFFs and overlay PNGs.

**Reasons**:
- S3-compatible API means production migration to AWS S3 requires only
  endpoint and credential changes
- Docker Compose service with persistent volume for local development
- Originals and overlays are stored in separate buckets for IAM clarity

**Trade-offs**: Adds one more Docker service to the local stack.

---

## ADR-006: HashiCorp Vault Dev Mode for Secrets

**Decision**: Use Vault KV v2 in dev mode for local secret management.

**Reasons**:
- Keeps all credentials out of `.env` files and out of Git
- Simulates a production-grade secret store in a local environment
- Required secrets: JWT_SECRET, DB credentials, MinIO credentials,
  SFTP credentials

**Caveats**: Vault dev mode stores data in memory only and reseeds on
restart. **Not for production use.** See [SECURITY.md](SECURITY.md).

---

## ADR-007: Casbin for Authorization

**Decision**: Use Casbin with the SQLAlchemy adapter for RBAC.

**Reasons**:
- Policies are stored in Postgres alongside application data — no
  separate policy service required
- Role matrix can be updated at runtime via admin API without a redeploy
- Enforcer is called in services, not in routers, keeping HTTP layer thin

**Role Matrix**:

| Action | admin | reviewer | auditor |
|---|---|---|---|
| List/read batches | ✅ | ✅ | ✅ |
| Read prediction detail | ✅ | ✅ | ✅ |
| Relabel prediction | ❌ | ✅ (confidence < 0.7 only) | ❌ |
| Read audit events | ✅ | ❌ | ✅ |
| Invite users | ✅ | ❌ | ❌ |
| Assign/revoke roles | ✅ | ❌ | ❌ |

---

## ADR-008: fastapi-cache2 with Redis Backend

**Decision**: Use fastapi-cache2 for read-mostly API response caching.

**Reasons**:
- Decorator-based caching integrates with FastAPI route handlers
- Redis backend is already present for RQ — no additional service required
- Cache keys include role context to prevent data leakage across roles

**Rules**:
- Services invalidate after commit — never routers or repositories
- Redis failure on invalidation is logged but does not roll back Postgres

---

## ADR-009: ConvNeXt Tiny or Small Classifier

**Decision**: Use torchvision ConvNeXt Tiny or Small for document layout
classification.

**Reasons**:
- Pretrained weights available from torchvision model zoo
- Sufficient accuracy for 16-class RVL-CDIP classification task
- Smaller memory footprint than ResNet-50 at comparable accuracy

**Constraints**:
- `model_card.json` must declare exactly 16 RVL-CDIP labels
- Checksum of `classifier.pt` is validated against `model_card.json`
  on inference worker startup
- Preprocessing settings must match the model card specification

---

## ADR-010: Separate Ingestion and Inference Workers

**Decision**: Run ingestion and inference as two separate worker processes.

**Reasons**:
- Ingestion is I/O bound (SFTP, MinIO, Postgres); inference is CPU/GPU bound
- Separating them allows independent scaling and restart policies
- Inference worker loads the classifier model once at startup and keeps it
  in memory; combining with ingestion would waste memory when idle

---

## ADR-011: Append-Only Audit Events

**Decision**: `audit_events` rows are never updated or deleted.

**Reasons**:
- Immutable audit trail is a security and compliance requirement
- No `actor_user_id` foreign key — allows user deletion without losing history
- System events (no actor) are recorded with `actor_user_id = NULL`
