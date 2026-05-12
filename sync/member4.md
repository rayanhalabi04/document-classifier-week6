# Member 4 — Classifier/Workers/Cache/CI

## Done

- **T001** — RVL-CDIP label contract + `model_card.json` validation (`app/classifier/validation.py`, `app/domain/model_metadata.py`)
- **T002** — ConvNeXt Tiny/Small model loader (`app/classifier/loader.py`)
- **T003** — Grayscale TIFF preprocessing (`app/classifier/preprocessing.py`)
- **T004** — Inference output mapping + confidence (`app/classifier/inference.py`)
- **T005** — Overlay PNG generation (`app/classifier/overlays.py`)
- **T006** — Golden-set replay (`app/classifier/golden_replay.py`)
- **T031** — Redis 7 adapter — sync + async clients, health check (`app/infra/redis.py`)
- **T032** — RQ queue adapter (`app/infra/queue.py`)
- **T033** — fastapi-cache2 setup + `delete_cache_key` (`app/infra/cache.py`), wired into FastAPI lifespan (`app/main.py`)
- **T042** — GitHub Actions lint + unit test CI stages (`.github/workflows/ci.yml`)
- **T056** — flake8 config (`backend/.flake8`)

All above tasks have unit tests and passed locally.

## Remaining

- **T028** — Inference worker startup validation — **blocked on Member 3** (MinIO adapter) + **Member 2** (DB session)
- **T029** — RQ job consumption + retry — **blocked on Member 2** (classification_jobs service)
- **T030** — Inference persistence flow — **blocked on Member 2** (prediction/job repositories)
- **T037** — Overlay PNG storage in MinIO — **blocked on Member 3** (MinIO adapter)
- **T043** — GitHub Actions service-backed stages — **blocked on Member 3** (Docker Compose)
- **T044** — Golden-set + compose smoke CI — **blocked on Member 3** (Docker Compose)
- **T059** — Secret scanning gate (gitleaks)
- **T062** — pytest coverage config (already in pyproject.toml, needs verification)
- **T063** — Dependency pinning + audit gate
- **T064** — Pre-commit quality pipeline

## Notes for teammates

- `app/infra/redis.py` exports `get_redis_client()` (sync) and `get_async_redis_client()` (async) — use these instead of creating your own Redis connections.
- `app/services/cache_invalidation.py` is ready to use — call `invalidate_after_classification()` or `invalidate_after_relabel()` after commits.
- `app/infra/queue.py` exports `enqueue_classification_job(document_id, model_metadata_id)` for the ingestion worker.
- Classifier assets are at `backend/app/classifier/models/` (classifier.pt via Git LFS).
- Golden fixtures are at `backend/tests/golden/fixtures/`.
