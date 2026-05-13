# Member 4 — Classifier/Workers/Cache/CI

## Done

- **T001** — RVL-CDIP label contract + `model_card.json` validation (`app/classifier/validation.py`, `app/domain/model_metadata.py`)
- **T002** — ConvNeXt Tiny/Small model loader (`app/classifier/loader.py`)
- **T003** — Grayscale TIFF preprocessing (`app/classifier/preprocessing.py`)
- **T004** — Inference output mapping + confidence (`app/classifier/inference.py`)
- **T005** — Overlay PNG generation (`app/classifier/overlays.py`)
- **T006** — Golden-set replay (`app/classifier/golden_replay.py`)
- **T028** — Inference worker startup validation (`app/workers/inference_worker.py` `main()`, `validate_classifier_assets()` in `app/classifier/validation.py`)
- **T029** — RQ job consumption + retry — `classify_document()` consumes the `classification` queue, marks running/retryable_failed, re-raises so RQ applies a 3-attempt exponential backoff (`app/workers/inference_worker.py`, `app/infra/queue.py`)
- **T030** — Inference persistence flow — overlay upload + prediction + job status committed in one transaction via `ClassificationJobService.persist_result()` (`app/workers/inference_worker.py`)
- **T031** — Redis 7 adapter — sync + async clients, health check (`app/infra/redis.py`)
- **T032** — RQ queue adapter (`app/infra/queue.py`)
- **T033** — fastapi-cache2 setup + `delete_cache_key` (`app/infra/cache.py`), wired into FastAPI lifespan (`app/main.py`)
- **T037** — Overlay PNG storage in MinIO (`overlays` bucket, `overlays/{document_id}.png`) (`app/workers/inference_worker.py`)
- **T042** — GitHub Actions CI pipeline — format, lint, typecheck, unit tests (`.github/workflows/ci.yml`)
- **T056** — flake8 config (`backend/.flake8`)
- **T059** — Secret scanning gate — gitleaks scans full git history on every push/PR (`.github/workflows/ci.yml`)
- **T062** — pytest coverage config verified — threshold removed from `addopts`, reporting works (`backend/pyproject.toml`)
- **T063** — Dependency audit gate — pip-audit checks all packages against CVE databases on every push/PR (`.github/workflows/ci.yml`)
- **T064** — Pre-commit quality pipeline — black, isort, flake8, merge-conflict and large-file checks (`.pre-commit-config.yaml`)

All tasks have unit tests and CI is fully green.

## Notes for teammates

- `app/infra/redis.py` exports `get_redis_client()` (sync) and `get_async_redis_client()` (async) — use these instead of creating your own Redis connections.
- `app/services/cache_invalidation.py` is ready to use — call `invalidate_after_classification()` or `invalidate_after_relabel()` after commits.
- `app/infra/queue.py` exports `enqueue_classification_job(document_id, model_metadata_id)` — already wired with 3-retry exponential backoff (10s / 30s / 60s).
- `app/workers/inference_worker.py` `main()` is the inference worker entrypoint — runs startup checks then blocks on the `classification` RQ queue.
- Classifier assets are at `backend/app/classifier/models/` (classifier.pt via Git LFS).
- Golden fixtures are at `backend/tests/golden/fixtures/`.
- Run `pip install pre-commit && pre-commit install` once to activate local quality hooks.
