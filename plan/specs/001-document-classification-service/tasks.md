# Tasks: Internal Document Classification Service

**Input**: Implementation plan from `/specs/001-document-classification-service/plan.md`
**Scope**: Task generation only. Do not implement code yet.

## Owners

- **Member 1**: API/Auth/Permissions
- **Member 2**: Services/Repositories/Database
- **Member 3**: Infrastructure, SFTP, MinIO, Vault, Docker Compose
- **Member 4**: Classifier, workers, cache/queue, CI

## Classifier and Golden-Set Evaluation

- [ ] T001 [P] Define RVL-CDIP label contract and classifier metadata validation
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `app/domain/predictions.py`, `app/domain/model_metadata.py`, `app/classifier/validation.py`, `tests/unit/test_classifier_validation.py`
  - **Acceptance criteria**: `model_card.json` validation rejects missing labels, non-16-class label lists, unsupported architecture values, and checksum mismatches.

- [ ] T002 [P] Plan ConvNeXt Tiny/Small model loader behavior
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `app/classifier/loader.py`, `tests/unit/test_classifier_loader.py`
  - **Acceptance criteria**: Loader accepts only `convnext_tiny` or `convnext_small`, loads `classifier.pt`, sets eval mode, and reports model identity without running API inference.

- [ ] T003 [P] Define grayscale TIFF preprocessing requirements
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `app/classifier/preprocessing.py`, `tests/unit/test_preprocessing.py`
  - **Acceptance criteria**: Preprocessing handles valid grayscale TIFFs, rejects unreadable or unsupported files, and produces tensors matching the model-card input shape.

- [ ] T004 [P] Define inference output mapping and confidence calculation
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `app/classifier/inference.py`, `tests/unit/test_inference_mapping.py`
  - **Acceptance criteria**: Inference returns exactly one top RVL-CDIP class, top-1 confidence, full class-score mapping, and deterministic label mapping.

- [ ] T005 [P] Define overlay PNG generation behavior
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `app/classifier/overlays.py`, `tests/unit/test_overlays.py`
  - **Acceptance criteria**: Overlay generation produces a PNG linked to the source document and prediction, and failures are reportable to the inference worker.

- [ ] T006 Create golden-set replay task plan
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `app/classifier/golden_replay.py`, `tests/golden/test_golden_replay.py`, `tests/golden/fixtures/`
  - **Acceptance criteria**: Golden replay loads `classifier.pt` and `model_card.json`, runs fixture documents, compares expected labels, and emits CI-readable pass/fail results.

## API/Auth/Permissions

- [ ] T007 [P] Define FastAPI application and router registration plan
  - **Owner suggestion**: Member 1
  - **Files likely affected**: `app/main.py`, `app/api/__init__.py`, `tests/contract/test_openapi_contract.py`
  - **Acceptance criteria**: OpenAPI includes auth, users, roles, batches, predictions, audit, and health routes; it includes no inference endpoint.

- [ ] T008 [P] Define fastapi-users JWT authentication setup
  - **Owner suggestion**: Member 1
  - **Files likely affected**: `app/api/auth.py`, `app/repositories/users.py`, `tests/contract/test_auth_contract.py`
  - **Acceptance criteria**: JWT login route, current-user behavior, inactive-user rejection, and JWT-secret validation are covered by contract tests.

- [ ] T009 [P] Define Casbin role policy model and baseline policies
  - **Owner suggestion**: Member 1
  - **Files likely affected**: `app/infra/casbin.py`, `app/domain/roles.py`, `tests/unit/test_permissions.py`
  - **Acceptance criteria**: Admin, reviewer, and auditor permissions match the spec and deny unauthorized writes.

- [ ] T010 Define admin user and role-management endpoints
  - **Owner suggestion**: Member 1
  - **Files likely affected**: `app/api/users.py`, `app/api/roles.py`, `tests/contract/test_admin_contract.py`
  - **Acceptance criteria**: Admin can invite users, list users, and replace/toggle roles; non-admin users receive denied responses.

- [ ] T011 Define batch and prediction read endpoints
  - **Owner suggestion**: Member 1
  - **Files likely affected**: `app/api/batches.py`, `app/api/predictions.py`, `tests/contract/test_batches_predictions_contract.py`
  - **Acceptance criteria**: Admin, reviewer, and auditor can list batches and read prediction detail with role-safe response models.

- [ ] T012 Define reviewer relabel endpoint
  - **Owner suggestion**: Member 1
  - **Files likely affected**: `app/api/predictions.py`, `tests/contract/test_prediction_review_contract.py`
  - **Acceptance criteria**: Reviewer can relabel only predictions below 0.7 confidence; high-confidence and unauthorized relabel attempts are rejected.

- [ ] T013 Define audit-log endpoint access
  - **Owner suggestion**: Member 1
  - **Files likely affected**: `app/api/audit.py`, `tests/contract/test_audit_contract.py`
  - **Acceptance criteria**: Admin and auditor can read audit logs with filters; reviewer access is denied unless explicitly allowed by policy.

- [ ] T014 [P] Define health and readiness endpoints
  - **Owner suggestion**: Member 1
  - **Files likely affected**: `app/api/health.py`, `app/services/startup_validation.py`, `tests/contract/test_health_contract.py`
  - **Acceptance criteria**: `/health/live` reports process liveness and `/health/ready` reports dependency and startup validation status.

## Services/Repositories/Database

- [ ] T015 Define SQLAlchemy 2.x ORM schema
  - **Owner suggestion**: Member 2
  - **Files likely affected**: `app/db/models.py`, `tests/repository/test_models.py`
  - **Acceptance criteria**: ORM includes `users`, `role_assignments`, `casbin_rule`, `batches`, `documents`, `classification_jobs`, `model_metadata`, `predictions`, `overlay_assets`, and `audit_events`.

- [ ] T016 Define Alembic migration plan
  - **Owner suggestion**: Member 2
  - **Files likely affected**: `alembic.ini`, `alembic/env.py`, `alembic/versions/001_initial_schema.py`, `tests/repository/test_migrations.py`
  - **Acceptance criteria**: Empty Postgres 16 database can upgrade to head and contains all required tables, constraints, and indexes.

- [ ] T017 [P] Define repository interfaces for core entities
  - **Owner suggestion**: Member 2
  - **Files likely affected**: `app/repositories/batches.py`, `app/repositories/documents.py`, `app/repositories/jobs.py`, `app/repositories/predictions.py`, `app/repositories/audit_events.py`
  - **Acceptance criteria**: Repositories contain SQL-only operations and do not import API, service, cache, worker, or classifier modules.

- [ ] T018 [P] Define user and role repositories
  - **Owner suggestion**: Member 2
  - **Files likely affected**: `app/repositories/users.py`, `app/repositories/roles.py`, `tests/repository/test_user_role_repositories.py`
  - **Acceptance criteria**: User lookup, invitation state, active roles, role replacement, and duplicate active-role prevention are testable.

- [ ] T019 Define ingestion service transaction boundaries
  - **Owner suggestion**: Member 2
  - **Files likely affected**: `app/services/ingestion.py`, `tests/service/test_ingestion_service.py`
  - **Acceptance criteria**: Document record, original object reference, queue job, audit event, and cache invalidation are coordinated with clear commit behavior.

- [ ] T020 Define classification job service behavior
  - **Owner suggestion**: Member 2
  - **Files likely affected**: `app/services/classification_jobs.py`, `tests/service/test_classification_jobs_service.py`
  - **Acceptance criteria**: Job states support queued, running, succeeded, retryable failure, and terminal failure without duplicate active jobs.

- [ ] T021 Define prediction review service behavior
  - **Owner suggestion**: Member 2
  - **Files likely affected**: `app/services/prediction_review.py`, `tests/service/test_prediction_review_service.py`
  - **Acceptance criteria**: Review preserves original prediction, records reviewer label and reviewer identity, rejects confidence >= 0.7, audits changes, and invalidates affected caches.

- [ ] T022 Define audit service behavior
  - **Owner suggestion**: Member 2
  - **Files likely affected**: `app/services/audit_log.py`, `tests/service/test_audit_log_service.py`
  - **Acceptance criteria**: Authentication, authorization failures, ingestion, classification, relabeling, role changes, and audit reads produce append-only audit events.

- [ ] T023 [P] Define startup validation service behavior
  - **Owner suggestion**: Member 2
  - **Files likely affected**: `app/services/startup_validation.py`, `tests/unit/test_startup_validation.py`
  - **Acceptance criteria**: API, ingestion worker, and inference worker readiness rules match `plan.md` and fail fast on missing dependencies.

## SFTP Ingestion Worker

- [ ] T024 [P] Define Atmoz SFTP connection and polling adapter
  - **Owner suggestion**: Member 3
  - **Files likely affected**: `app/infra/sftp.py`, `tests/unit/test_sftp_adapter.py`
  - **Acceptance criteria**: Adapter lists vendor drop files, reads file metadata, streams file content, and reports connection or permission failures.

- [ ] T025 Define stable-file detection behavior
  - **Owner suggestion**: Member 3
  - **Files likely affected**: `app/services/ingestion.py`, `tests/service/test_ingestion_file_stability.py`
  - **Acceptance criteria**: Worker avoids ingesting files still being written by requiring stable size and modified timestamp across polling intervals.

- [ ] T026 Define duplicate and invalid-file handling
  - **Owner suggestion**: Member 3
  - **Files likely affected**: `app/services/ingestion.py`, `app/repositories/documents.py`, `tests/service/test_ingestion_edge_cases.py`
  - **Acceptance criteria**: Duplicate source/checksum combinations do not create duplicate active predictions; corrupted or non-TIFF files are marked failed and audited.

- [ ] T027 Define ingestion worker loop
  - **Owner suggestion**: Member 3
  - **Files likely affected**: `app/workers/ingestion_worker.py`, `tests/integration/test_ingestion_worker_flow.py`
  - **Acceptance criteria**: Worker polls SFTP, stores accepted originals in MinIO, enqueues RQ jobs, records document/job state, and continues after per-file failures.

## Inference Worker

- [ ] T028 Define inference worker startup sequence
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `app/workers/inference_worker.py`, `app/services/startup_validation.py`, `tests/unit/test_inference_worker_startup.py`
  - **Acceptance criteria**: Worker validates classifier asset, model card, label count, output dimension, MinIO access, Postgres access, and Redis Queue access before consuming jobs.

- [ ] T029 Define RQ job consumption and retry behavior
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `app/workers/inference_worker.py`, `app/services/classification_jobs.py`, `tests/integration/test_inference_retries.py`
  - **Acceptance criteria**: Job attempts are tracked, retryable failures are requeued or marked, and terminal failures are visible to operators.

- [ ] T030 Define inference persistence flow
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `app/workers/inference_worker.py`, `app/services/classification_jobs.py`, `app/repositories/predictions.py`, `tests/integration/test_inference_worker_flow.py`
  - **Acceptance criteria**: Successful jobs persist prediction, class scores, confidence, review eligibility, model metadata, overlay asset location, job success, audit event, and cache invalidation.

## Redis Cache and Queue

- [ ] T031 [P] Define Redis 7 connection adapter
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `app/infra/redis.py`, `tests/unit/test_redis_adapter.py`
  - **Acceptance criteria**: Redis adapter supports cache and RQ clients with health checks and configurable local URLs.

- [ ] T032 [P] Define RQ queue adapter
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `app/infra/queue.py`, `tests/unit/test_queue_adapter.py`
  - **Acceptance criteria**: Queue adapter enqueues classification jobs with document IDs only and exposes job IDs for `classification_jobs`.

- [ ] T033 Define fastapi-cache2 Redis backend setup
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `app/infra/cache.py`, `app/services/cache_invalidation.py`, `tests/unit/test_cache_invalidation.py`
  - **Acceptance criteria**: Cache keys include role context where needed and support invalidation for batch list, batch detail, prediction detail, audit list, and user roles.

- [ ] T034 Define post-commit cache invalidation rules
  - **Owner suggestion**: Member 2
  - **Files likely affected**: `app/services/cache_invalidation.py`, `tests/service/test_cache_after_commit.py`
  - **Acceptance criteria**: Services invalidate only after successful persistence; Redis deletion failures do not roll back authoritative Postgres data.

## MinIO Blob Storage

- [ ] T035 [P] Define MinIO bucket bootstrap behavior
  - **Owner suggestion**: Member 3
  - **Files likely affected**: `app/infra/minio.py`, `app/services/startup_validation.py`, `tests/unit/test_minio_bootstrap.py`
  - **Acceptance criteria**: Original and overlay buckets are created or validated during startup and report readiness failures clearly.

- [ ] T036 Define original TIFF storage behavior
  - **Owner suggestion**: Member 3
  - **Files likely affected**: `app/infra/minio.py`, `app/services/ingestion.py`, `tests/service/test_original_storage.py`
  - **Acceptance criteria**: Accepted originals are uploaded before queueing and document records store bucket/key metadata.

- [ ] T037 Define overlay PNG storage behavior
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `app/infra/minio.py`, `app/classifier/overlays.py`, `app/repositories/predictions.py`, `tests/service/test_overlay_storage.py`
  - **Acceptance criteria**: Overlay PNGs are stored with prediction linkage and can be referenced by prediction detail responses.

## Vault Secrets

- [ ] T038 [P] Define Vault dev mode KV v2 adapter
  - **Owner suggestion**: Member 3
  - **Files likely affected**: `app/infra/vault.py`, `tests/unit/test_vault_adapter.py`
  - **Acceptance criteria**: Adapter reads required secret paths for JWT, SFTP, MinIO, Postgres, and Redis and reports missing keys.

- [ ] T039 Define local Vault bootstrap expectations
  - **Owner suggestion**: Member 3
  - **Files likely affected**: `docker-compose.yml`, `RUNBOOK.md`, `SECURITY.md`
  - **Acceptance criteria**: Local runbook explains Vault dev mode, KV v2 mount, seeded secrets, and why dev mode is not production-safe.

## CI and Docker Compose

- [ ] T040 Define Docker Compose local stack
  - **Owner suggestion**: Member 3
  - **Files likely affected**: `docker-compose.yml`, `.env.example`, `RUNBOOK.md`
  - **Acceptance criteria**: Compose includes api, ingestion-worker, inference-worker, postgres:16, redis:7, minio, vault dev mode, and atmoz/sftp services.

- [ ] T041 [P] Define API and worker Docker image build behavior
  - **Owner suggestion**: Member 3
  - **Files likely affected**: `Dockerfile`, `.dockerignore`, `RUNBOOK.md`
  - **Acceptance criteria**: API and workers can share the image while using distinct commands and read-only classifier asset mounts where appropriate.

- [ ] T042 Define GitHub Actions lint and unit-test stages
  - **Owner suggestion**: Member 1
  - **Files likely affected**: `.github/workflows/ci.yml`, `pyproject.toml`
  - **Acceptance criteria**: CI runs formatting/lint checks, static checks where configured, and unit tests without external services.

- [ ] T043 Define GitHub Actions service-backed stages
  - **Owner suggestion**: Member 1
  - **Files likely affected**: `.github/workflows/ci.yml`
  - **Acceptance criteria**: CI starts Postgres 16, Redis 7, MinIO, Vault dev mode, and Atmoz SFTP for migration, contract, integration, and worker tests.

- [ ] T044 Define golden-set and compose smoke CI stages
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `.github/workflows/ci.yml`, `tests/golden/test_golden_replay.py`, `RUNBOOK.md`
  - **Acceptance criteria**: CI runs golden-set replay and a Docker Compose smoke check against `/health/live` and `/health/ready`.

## Documentation and Presentation

- [ ] T045 [P] Update architecture documentation
  - **Owner suggestion**: Member 2
  - **Files likely affected**: `ARCH.md`
  - **Acceptance criteria**: Document explains module boundaries, worker flow, storage, cache, queue, and why API does not run inference.

- [ ] T046 [P] Update decision log
  - **Owner suggestion**: Member 2
  - **Files likely affected**: `DECISIONS.md`
  - **Acceptance criteria**: Decisions cover FastAPI, SQLAlchemy 2.x, RQ, MinIO, Vault dev mode, Atmoz SFTP, Casbin, fastapi-cache2, and ConvNeXt.

- [ ] T047 [P] Update runbook
  - **Owner suggestion**: Member 3
  - **Files likely affected**: `RUNBOOK.md`
  - **Acceptance criteria**: New contributor can start services, run migrations, seed users/secrets, drop a TIFF, inspect results, run tests, and troubleshoot common failures.

- [ ] T048 [P] Update security documentation
  - **Owner suggestion**: Member 1
  - **Files likely affected**: `SECURITY.md`
  - **Acceptance criteria**: Document covers JWT handling, Vault dev-mode caveats, role permissions, audit events, local-only scope, and secret hygiene.

- [ ] T049 [P] Prepare presentation/demo checklist
  - **Owner suggestion**: Member 3
  - **Files likely affected**: `RUNBOOK.md`, `COLLABORATION.md`
  - **Acceptance criteria**: Checklist covers local stack startup, SFTP drop, classification result, reviewer relabel, admin role change, auditor read-only access, and CI status.

## Collaboration/Trello

- [ ] T050 [P] Define Trello board structure
  - **Owner suggestion**: Member 1
  - **Files likely affected**: `COLLABORATION.md`
  - **Acceptance criteria**: Board lists include Backlog, Ready, In Progress, Review, Blocked, Done, and Demo Prep.

- [ ] T051 [P] Map workstreams to four members
  - **Owner suggestion**: Member 1
  - **Files likely affected**: `COLLABORATION.md`
  - **Acceptance criteria**: Ownership maps Member 1 to API/Auth/Permissions, Member 2 to Services/Repositories/Database, Member 3 to Infra/SFTP/MinIO/Vault/Compose, and Member 4 to Classifier/Workers/Cache/CI.

- [ ] T052 [P] Define Trello card acceptance template
  - **Owner suggestion**: Member 1
  - **Files likely affected**: `COLLABORATION.md`
  - **Acceptance criteria**: Each card template includes title, owner, files likely affected, acceptance criteria, tests, blockers, and demo notes.

- [ ] T053 Define integration review checkpoints
  - **Owner suggestion**: Member 2
  - **Files likely affected**: `COLLABORATION.md`
  - **Acceptance criteria**: Checkpoints exist for schema freeze, API contract freeze, worker end-to-end demo, review/admin/auditor demo, and final presentation readiness.

## Repository Standards and Quality Gates

- [ ] T054 [P] Define CONTRIBUTING workflow for branches, commits, and pull requests
  - **Owner suggestion**: Member 1
  - **Files likely affected**: `CONTRIBUTING.md`, `README.md`, `COLLABORATION.md`
  - **Acceptance criteria**: Documentation defines branch naming, no direct commits to `main`, Conventional Commits, PR review rules, required test evidence, and Trello card linkage.

- [ ] T055 [P] Add GitHub pull request template requirements
  - **Owner suggestion**: Member 1
  - **Files likely affected**: `.github/pull_request_template.md`, `CONTRIBUTING.md`
  - **Acceptance criteria**: Template includes summary, linked task/Trello card, files changed, test evidence, security impact, documentation impact, screenshots/logs when relevant, and reviewer checklist.

- [ ] T056 [P] Configure black, isort, flake8, and mypy quality tools
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `pyproject.toml`, `.flake8`, `mypy.ini`, `.github/workflows/ci.yml`
  - **Acceptance criteria**: Tool configuration is documented and CI can run `black --check`, `isort --check-only`, `flake8`, and `mypy` as separate failing gates.

- [ ] T057 [P] Document Python naming and Google-style docstring standards
  - **Owner suggestion**: Member 2
  - **Files likely affected**: `CONTRIBUTING.md`, `README.md`
  - **Acceptance criteria**: Standards cover `snake_case` modules/functions, `PascalCase` classes, `UPPER_SNAKE_CASE` constants, private helper naming, and Google-style docstrings for public modules/classes/functions.

- [ ] T058 [P] Define repository ignore files
  - **Owner suggestion**: Member 3
  - **Files likely affected**: `.gitignore`, `.dockerignore`, `CONTRIBUTING.md`
  - **Acceptance criteria**: Ignore rules exclude virtual environments, caches, logs, local `.env` files, local service data, generated coverage artifacts, IDE metadata, Git metadata from Docker builds, and local secrets.

- [ ] T059 [P] Add secret scanning gate with gitleaks or equivalent
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `.github/workflows/ci.yml`, `.gitleaks.toml`, `SECURITY.md`, `CONTRIBUTING.md`
  - **Acceptance criteria**: CI or documented pre-merge checks scan for committed credentials, tokens, private keys, `.env` content, JWT secrets, MinIO credentials, Vault tokens, and SFTP credentials.

- [ ] T060 Define safe error-handling foundation
  - **Owner suggestion**: Member 2
  - **Files likely affected**: `app/domain/errors.py`, `app/services/startup_validation.py`, `app/api/health.py`, `CONTRIBUTING.md`, `tests/unit/test_error_handling.py`
  - **Acceptance criteria**: Plan defines typed domain/application errors, no bare `except`, safe user-facing messages, no leaked secrets or stack traces, and test coverage for representative failure paths.

- [ ] T061 Define structured logging foundation
  - **Owner suggestion**: Member 2
  - **Files likely affected**: `app/infra/logging.py`, `app/main.py`, `app/workers/ingestion_worker.py`, `app/workers/inference_worker.py`, `tests/unit/test_logging_context.py`
  - **Acceptance criteria**: Logging plan includes request IDs for API requests, job IDs for worker jobs, safe contextual IDs such as batch/document/prediction/user IDs, and no sensitive values in logs.

- [ ] T062 [P] Configure pytest coverage with 80% target
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `pyproject.toml`, `.coveragerc`, `.github/workflows/ci.yml`, `CONTRIBUTING.md`
  - **Acceptance criteria**: Test configuration records coverage for `app/`, sets an 80% minimum target, and documents coverage expectations for domain, service, repository, API contract, worker, and classifier paths.

- [ ] T063 [P] Define dependency pinning and dependency audit gate
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `pyproject.toml`, dependency lock file, `.github/workflows/ci.yml`, `SECURITY.md`
  - **Acceptance criteria**: Dependencies are pinned or locked, local and CI installs are reproducible, and CI or release checklist runs a dependency audit that fails on critical vulnerabilities unless explicitly accepted.

- [ ] T064 [P] Define pre-commit quality pipeline
  - **Owner suggestion**: Member 4
  - **Files likely affected**: `.pre-commit-config.yaml`, `CONTRIBUTING.md`, `README.md`
  - **Acceptance criteria**: Pre-commit plan runs formatting, import sorting, linting, type checks where practical, secret scanning, trailing whitespace checks, and YAML/Markdown hygiene checks before commit.

- [ ] T065 [P] Add documentation checklist for repository readiness
  - **Owner suggestion**: Member 1
  - **Files likely affected**: `README.md`, `CONTRIBUTING.md`, `ARCH.md`, `DECISIONS.md`, `RUNBOOK.md`, `SECURITY.md`, `COLLABORATION.md`
  - **Acceptance criteria**: Checklist verifies required docs exist and cover local setup, project architecture, coding standards, PR workflow, security expectations, runbook commands, decisions, collaboration, and demo/presentation notes.

## Dependency Notes

- Database schema, settings, and Docker Compose planning unblock most other streams.
- API/Auth/Permissions can progress with mocked repositories once table contracts are stable.
- Classifier validation and golden-set work can progress before worker orchestration.
- SFTP ingestion, MinIO storage, Redis queue, and inference worker converge in the end-to-end worker flow.
- Repository standards and quality gates can start immediately after planning and should be in place before feature implementation PRs.
- Documentation and Trello setup can run in parallel but must be updated after final integration decisions.
