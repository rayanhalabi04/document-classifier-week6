# Member 3 — Infrastructure, SFTP, MinIO, Vault, Docker Compose

## Done

### T058 — Repository ignore files
- `.gitignore` — excludes venv, .env, IDE, coverage, Docker volumes, `sftp_drop/`
- `.dockerignore` — excludes .git, tests, IDE, plan/, docs/, logs

### T040 — Docker Compose local stack
- `docker-compose.yml` — **9 services**: postgres:16, redis:7, minio, vault, atmoz/sftp, pgadmin, api, ingestion-worker, inference-worker
- Healthchecks on postgres (pg_isready), redis (ping), minio (health/live), vault (status)
- Shared bridge network `classifier-net`
- Persisted volumes: postgres_data, minio_data, vault_data, pgadmin_data
- Classifier assets mounted read-only (`backend/app/classifier/models/classifier.pt`, `model_card.json`)
- SFTP uses bind mount (`./sftp_drop`) — no manual chown needed
- pgAdmin auto-registers server via `pgadmin_servers.json`
- `backend/.env.example` — 16 environment variables covering all services

### T041 — Dockerfile
- `backend/Dockerfile` — Python 3.11-slim, apt libgl1+tiff deps, shared image for api + both workers
- Classifier weights NOT in image (volume-mounted)
- Non-root user (appuser)

### T038 — Vault adapter
- `app/infra/vault.py` — VaultAdapter: `read_secret(path, key)`, `validate_required_secrets()`
- Covers 5 paths: jwt, postgres, minio, sftp, redis (13 keys total)
- Typed errors: VaultConnectionError, VaultSecretNotFound, VaultKeyNotFound
- 12 unit tests passing

### T024 — SFTP adapter
- `app/infra/sftp.py` — SFTPAdapter: `list_files()`, `get_file_metadata()`, `open_file()` (streaming), `read_file_content()`
- Context-manager pattern via Paramiko
- Typed errors: SFTPConnectionError, SFTPPermissionError, SFTPFileError
- 16 unit tests passing

### T035 — MinIO adapter
- `app/infra/minio.py` — MinIOAdapter: `ensure_buckets_exist()`, `upload_file()`, `download_file()`, `file_exists()`
- Bucket bootstrap: idempotent create/validate for originals + overlays
- Typed errors: MinIOConnectionError, MinIOPermissionError, MinIOBucketError, MinIOFileNotFoundError
- 14 unit tests passing

### T025 — Stable-file detection
- `app/workers/ingestion_worker.py` — `_detect_stable_files()` compares size+mtime across polls

### T026 — Duplicate and invalid-file handling
- `app/workers/ingestion_worker.py` — `_process_file()` handles TIFF validation, duplicates, storage failures

### T027 — Ingestion worker loop
- `app/workers/ingestion_worker.py` — `main()` with startup checks, poll cycle, per-file resilience

### T036 — Original TIFF storage in MinIO
- `app/infra/minio.py` — `upload_original()`, `ensure_buckets()`, `check_originals_writable()` module-level injection points
- `app/infra/sftp.py` — `check_connection()` startup check
- `app/infra/vault.py` — `validate_required_secrets()` module-level wrapper

### Injection points for other members
- `app/infra/queue.py` — `enqueue_classification_job()`, `check_queue_health()` (temp for M4)
- `app/infra/redis.py` — `get_redis_client()` (temp for M4)

### Bugfixes
- `Dockerfile` — libgl1+libtiff6 for Debian Trixie, uv pip install, CPU-only torch
- `pyproject.toml` — torch==2.3.0+cpu, torchvision==0.18.0+cpu, fix build-backend
- `docker-compose.yml` — vault healthcheck `-address=http://127.0.0.1:8200`
- `alembic/versions/001_initial_schema.py` — fix duplicate Postgres ENUM creation (details below)
- `.env.example` — resolve conflict markers, add DATABASE_URL, fix SFTP_DROP_DIR=drop

#### Alembic migration fix details

**Problem:** `alembic upgrade head` failed with `type "batchstatus" already exists`
on a fresh Postgres database. The migration (`001_initial_schema.py`) defined
standalone `sa.Enum()` variables (lines 22-33) AND inline `sa.Enum()` calls
inside `op.create_table()` (lines 115, 157, 200). Both registered `before_create`
DDL events. The standalone `.create()` at line 34 created the type successfully,
then `op.create_table()` at line 109 fired a second `before_create` event that
tried to `CREATE TYPE` again — duplicate object error.

**Fix:** Replaced the three inline `sa.Enum(...)` calls inside `op.create_table()`
with direct references to the standalone enum variables (`batchstatus`,
`ingestionstatus`, `jobstatus`). This ensures only one `before_create` event
handler exists per enum type, and the standalone `.create(op.get_bind())` calls
remain the authoritative type creators. Also added `checkfirst=True` to those
calls as a safety net.

**Member 2 note:** This is your file. Review this change — no data impact,
purely a DDL ordering fix. The migration now runs cleanly: `alembic upgrade head`
creates all 10 tables without errors.

### Extras
- `scripts/seed_vault.py` — seeds all 5 Vault paths, verifies them
- `scripts/seed_users.py` — creates initial admin user for local development
- `Makefile` — 12 targets
- `tests/integration/test_adapters_live.py` — 3 live tests against real Docker services
- pgAdmin at `localhost:5050` with pre-configured server
- `sync/member3.md` — this file

### End-to-end verified
```
SFTP drop → stable-file detection → TIFF validation → MinIO upload
→ Postgres document record → RQ job enqueued → classification_jobs created
```
Tested with golden-set TIFF (135KB). All startup checks pass. API healthy on :8000.

---

## Remaining

| Task | What | Status |
|------|------|--------|
| **T039** | Vault bootstrap docs | ⬜ Needs full system |
| **T047** | Runbook (`RUNBOOK.md`) | ⬜ Needs full system |
| **T049** | Presentation/demo checklist | ⬜ Needs full system |

---

## Blocked by

- **No blockers** — all 3 teammates have shipped their code. Full end-to-end pipeline is possible.
- Documentation tasks (T039, T047, T049) are now unblocked.

---

## Unblocked — Member 2 finished all blockers

| What we needed | File | Status |
|---------------|------|--------|
| Ingestion service (T019) | `app/services/ingestion.py` | Ready — `ingest_file()`, `mark_failed()` |
| Document repository (T017) | `app/repositories/documents.py` | Ready — `create()`, `find_active_duplicate()` |
| Startup validation (T023) | `app/services/startup_validation.py` | Ready — calls our Vault/MinIO checks |
| DB session | `app/db/session.py` | Ready — `SessionFactory()` |
| Domain errors | `app/domain/errors.py` | Ready — `DuplicateDocumentError`, `UnsupportedFileTypeError` |
| ORM models | `app/db/models.py` | Ready — all 10 tables with ENUMs |
| Alembic migration | `alembic/versions/001_initial_schema.py` | Ready — `alembic upgrade head` works |
