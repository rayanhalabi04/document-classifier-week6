# Runbook — Document Classification Service

How to start, operate, test, troubleshoot, and tear down the full local stack.

---

## Prerequisites

- Docker + Docker Compose v2
- Git LFS (`git lfs --version`)
- Make (optional — all Make targets have manual equivalents below)

---

## Quick Start (First Time)

```bash
# 1. Pull classifier model weights (107 MB, tracked via Git LFS)
git lfs pull

# 2. Create .env from template
cp backend/.env.example backend/.env

# 3. Start all services and rebuild images
docker compose up -d --build

# 4. Wait for all services healthy, then run migrations
docker compose run --rm api alembic upgrade head

# 5. Seed Vault secrets
docker compose run --rm api python scripts/seed_vault.py

# 6. Seed model metadata
docker compose run --rm api python scripts/seed_model_metadata.py

# 7. Create admin user
docker compose run --rm api python scripts/seed_users.py

# 8. Seed Casbin RBAC policies
docker compose run --rm api python scripts/seed_casbin_policies.py
```

Or use the one-shot Make target:

```bash
make setup
```

When complete, the API is live at `http://localhost:8000` and the frontend at `http://localhost:5173`.

---

## Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| **API** | http://localhost:8000 | Bearer token via `/auth/jwt/login` |
| **API Docs** | http://localhost:8000/docs | Auto-generated Swagger UI |
| **Frontend** | http://localhost:5173 | `admin@example.com` / `admin` |
| **pgAdmin** | http://localhost:5050 | `admin@example.com` / `admin` |
| **MinIO Console** | http://localhost:9001 | `minioadmin` / `minioadmin` |
| **MinIO S3 API** | http://localhost:9000 | `minioadmin` / `minioadmin` |
| **Vault** | http://localhost:8200 | Token: `root` |
| **SFTP** | `sftp://vendor@localhost:2222` | `vendor` / `vendorpass` |

---

## Day-to-Day Commands

```bash
# Start all services (no rebuild, uses cached images)
docker compose up -d

# Stop all services (preserves data)
docker compose down

# Tail all logs
docker compose logs -f

# Tail a specific service
docker compose logs -f ingestion-worker

# Check service status
docker compose ps

# Rebuild after code changes
docker compose up -d --build

# Restart a single service
docker compose restart api
```

Make equivalents:
```bash
make up          # docker compose up -d
make down        # docker compose down
make logs        # docker compose logs -f
make ps          # docker compose ps
```

---

## Testing

```bash
# Unit tests only (fast, no Docker needed — but Vault/SFTP tests need .env)
make test
# or:
cd backend && python -m pytest tests/unit/ -v

# Live integration tests (requires Docker services running)
make test-live
# or:
cd backend && python -m pytest tests/integration/test_adapters_live.py -v -s

# Full test suite
make test-all
# or:
cd backend && python -m pytest tests/ -v
```

Live integration tests verify:
- Vault: real connection, secret reads, validation
- MinIO: bucket creation, upload, download, existence checks
- SFTP: listing, file metadata, streaming reads

---

## Seeding Data

```bash
# Vault secrets (required for any app startup)
make seed
# or: docker compose run --rm api python scripts/seed_vault.py

# Admin user (idempotent — skips if exists)
make seed-users
# or: docker compose run --rm api python scripts/seed_users.py

# Everything (model metadata + users + Casbin policies)
make seed-all
# or: docker compose run --rm api python scripts/seed_model_metadata.py
#     docker compose run --rm api python scripts/seed_users.py
#     docker compose run --rm api python scripts/seed_casbin_policies.py
```

---

## Demo Account Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@example.com` | `admin` |
| Reviewer | `reviewer@example.com` | `reviewerpass` |
| Auditor | `auditor@example.com` | `auditorpass` |

The reviewer and auditor accounts are created by `seed_demo_users.py` (run via `docker compose run --rm api python scripts/seed_demo_users.py`).

---

## Testing the Pipeline End-to-End

```bash
# 1. Drop a TIFF file into the SFTP folder
cp test.tiff sftp_drop/

# 2. Watch the ingestion worker detect and process it
docker compose logs -f ingestion-worker
# Expected: "Stable file detected" → "Ingested" → "Enqueued classification job"

# 3. Watch the inference worker classify it
docker compose logs -f inference-worker
# Expected: "Running classification job" → "Prediction saved" → "Overlay uploaded"

# 4. Verify via API
curl -s http://localhost:8000/batches | python -m json.tool
curl -s http://localhost:8000/predictions/recent | python -m json.tool
```

Or use the frontend at http://localhost:5173 — login, navigate to Overview or Predictions.

---

## Health Checks

```bash
# API liveness (container alive?)
curl http://localhost:8000/health/live

# API readiness (all dependencies OK?)
curl http://localhost:8000/health/ready
```

All Docker services have `healthcheck` blocks. Check with:
```bash
docker compose ps  # "healthy" column
```

---

## Reset / Clean Tear Down

```bash
# Full reset: destroy all data and volumes, rebuild from scratch
make clean
# or:
docker compose down --volumes --remove-orphans
rm -rf sftp_drop/*
# Then: make setup
```

To reset without losing images:
```bash
make reset
# or:
docker compose down --volumes --remove-orphans
rm -rf sftp_drop/*
docker compose up -d
docker compose run --rm api python scripts/seed_vault.py
```

---

## Troubleshooting

### API returns 500 on startup

**Cause:** Missing Vault secrets.  
**Fix:** Run `make seed` (or `docker compose run --rm api python scripts/seed_vault.py`).  
**Check:** `curl http://localhost:8000/health/ready` — reports which secrets are missing.

### `alembic upgrade head` fails with "type already exists"

**Cause:** Old migration bug (fixed in `001_initial_schema.py`).  
**Fix:** Destroy volumes and start fresh: `make clean && make setup`.  
**Root cause:** Duplicate `sa.Enum()` objects tried to create the same Postgres type twice.

### Ingestion worker sees files but skips them

Check the worker logs:
- **"Not stable yet"** — file is still being written. Wait 2 poll cycles (10 seconds).
- **"Duplicate detected"** — same checksum already processed. Expected if you re-drop the same file.
- **"Unsupported file type"** — not a valid TIFF (magic bytes check failed).

### Inference worker never runs classification jobs

**Cause:** Redis might not be connected, or RQ worker isn't registered.  
**Check:** `docker compose logs inference-worker` — should show "Worker listening on queue: classification".  
**Ensure:** Redis healthcheck passes (`docker compose ps redis` shows healthy).

### "ModuleNotFoundError: No module named 'app'"

**Cause:** Old Docker image built with wrong layer order.  
**Fix:** Rebuild: `docker compose build --no-cache api` then `docker compose up -d`.  
**Note:** Fixed in current Dockerfile — `COPY app/` now comes before editable install.

### Vault healthcheck takes forever

**Cause:** `vault status` defaults to HTTPS, dev mode uses HTTP.  
**Fix:** Already set to `-address=http://127.0.0.1:8200` in `docker-compose.yml`.

### Port 5432 (Postgres) already in use

**Cause:** Local Postgres running on the host.  
**Fix:** Stop local Postgres, or change the port mapping in `docker-compose.yml` (line 9).

### Docker Hub DNS failures during build

**Cause:** Intermittent `auth.docker.io` lookup issues.  
**Workaround:** Use cached images: `docker compose up -d` (skip `--build`).  
**Alternative:** Retry with `docker compose build api` individually.

### `docker compose up --build` is slow (~5+ minutes)

**Cause:** Layer order in old Dockerfile caused pip install (including 130 MB torch) to re-run on every code change.  
**Fix:** Fixed — `pyproject.toml` is now copied and deps installed BEFORE code. Subsequent builds are fast (seconds).  
**First build still downloads torch once (~130 MB).**

### bcrypt warning on seed_users.py

```
UserWarning: 'bcrypt'... __about__ attribute deprecated
```

**Cause:** `passlib` incompatibility with newer `bcrypt` versions.  
**Impact:** None — users created successfully. The warning is harmless.

---

## File Locations

| What | Where |
|------|-------|
| Docker Compose | `./docker-compose.yml` |
| Backend Dockerfile | `./backend/Dockerfile` |
| Frontend Dockerfile | `./frontend/Dockerfile` |
| Environment template | `./backend/.env.example` |
| Vault seeder | `./backend/scripts/seed_vault.py` |
| User seeder | `./backend/scripts/seed_users.py` |
| Demo user seeder | `./backend/scripts/seed_demo_users.py` |
| Casbin policies | `./backend/scripts/seed_casbin_policies.py` |
| Model metadata seeder | `./backend/scripts/seed_model_metadata.py` |
| Alembic migrations | `./backend/alembic/versions/` |
| Classifier model | `./backend/app/classifier/models/classifier.pt` |
| Model card | `./backend/app/classifier/models/model_card.json` |
| Makefile | `./Makefile` |
| pgAdmin server config | `./pgadmin_servers.json` |
