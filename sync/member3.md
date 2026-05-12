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
- Classifier assets mounted read-only (`backend/models/classifier.pt`, `model_card.json`)
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

### Extras
- `scripts/seed_vault.py` — seeds all 5 Vault paths, verifies them
- `Makefile` — 12 targets: setup, up, down, test, test-live, test-all, reset, clean, seed, ps, logs, shell
- `tests/integration/test_adapters_live.py` — 3 live tests against real Docker services (all pass)
- pgAdmin at `localhost:5050` with pre-configured server

### Test totals
- 42 unit tests (all pass)
- 3 live integration tests (all pass)
- 27 Member 1's tests also pass alongside ours (72 total green)

---

## Remaining

| Task | What | Status |
|------|------|--------|
| **T025** | Stable-file detection (`app/services/ingestion.py`) | ⬜ Ready to start — Member 2's T019 done |
| **T026** | Duplicate/invalid-file handling (`app/services/ingestion.py`, `app/repositories/documents.py`) | ⬜ Ready to start — Member 2's T017+T019 done |
| **T027** | Ingestion worker loop (`app/workers/ingestion_worker.py`) | ⬜ Needs T025+T026+T036 first |
| **T036** | Original TIFF storage in MinIO (infra part done, service wiring pending) | ⬜ Ready to start — Member 2's T019 done |
| **T039** | Vault bootstrap docs (`docker-compose.yml` done, `RUNBOOK.md`/`SECURITY.md` pending) | ⬜ System end-to-end needed |
| **T047** | Runbook (`RUNBOOK.md`) | ⬜ System end-to-end needed |
| **T049** | Presentation/demo checklist | ⬜ System end-to-end needed |

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
