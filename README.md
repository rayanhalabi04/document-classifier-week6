# Document Classifier

Internal document classification service for the AIE Bootcamp Week 6 project.

A scanner vendor drops grayscale TIFF files into an SFTP server. The system
ingests them, classifies each document into one of 16 RVL-CDIP layout
categories using a ConvNeXt classifier, and exposes the results through an
authenticated REST API with reviewer relabeling and full audit logging.

---

## Local Setup

### Prerequisites

- Docker Desktop (with Compose v2)
- Git LFS (for classifier model weights)
- Python 3.11
- Git

### 1. Clone and configure

```bash
git clone <repo-url>
cd document-classifier-week6
git lfs pull
cp backend/.env.example backend/.env
# Edit backend/.env with your local values (see .env.example for required keys)
```

### 2. Create the virtual environment

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev]"
```

### 3. Start the Docker stack

```bash
docker compose up -d --build
```

Starts 10 services: postgres, redis, minio, vault, sftp, pgadmin, api, frontend,
ingestion-worker, inference-worker. All health-checked before starting.

| URL | Service |
|-----|---------|
| http://localhost:8000 | FastAPI |
| http://localhost:5173 | Frontend dashboard |
| http://localhost:5050 | pgAdmin |
| http://localhost:9001 | MinIO Console |
| http://localhost:8200 | Vault |

### 4. Run database migrations

```bash
docker compose run --rm api alembic upgrade head
```

### 5. Seed all data

```bash
docker compose run --rm api python scripts/seed_vault.py
docker compose run --rm api python scripts/seed_model_metadata.py
docker compose run --rm api python scripts/seed_users.py
docker compose run --rm api python scripts/seed_casbin_policies.py
docker compose run --rm api python scripts/seed_demo_users.py
```

Or use the one-shot Make target:

```bash
make setup   # runs all of the above + git lfs pull
```

### 6. Verify everything is running

```bash
curl http://localhost:8000/health/ready
# → {"status": "ok"}
```

### Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@example.com` | `admin` |
| Reviewer | `reviewer@example.com` | `reviewerpass` |
| Auditor | `auditor@example.com` | `auditorpass` |

Log in at http://localhost:5173.

See [docs/RUNBOOK.md](docs/RUNBOOK.md) for the full local workflow including
dropping a TIFF, checking classification results, and troubleshooting.

---

## Running Tests

```bash
cd backend

# All tests with coverage
pytest

# Fast unit tests only (no Docker services needed)
pytest tests/unit/

# Repository tests (requires Postgres)
pytest tests/repository/

# Service tests
pytest tests/service/

# API contract tests
pytest tests/contract/

# Integration tests (requires full Docker stack)
pytest tests/integration/

# Golden-set classifier replay
pytest tests/golden/
```

---

## Code Quality

```bash
# Format the full backend
black .

# Sort all backend imports
isort .

# Lint the full backend
flake8 .

# Type check
mypy app/

# Unit tests without coverage gates or external services
pytest tests/unit -q -o addopts=''
```

CI currently checks formatting and linting only on changed backend Python files so
unrelated legacy formatting does not block pull requests. Full-repo formatting,
linting, and type checking remain useful cleanup commands, but they are broader
than the T042 CI gate.

---

## Branch Naming

All branches must use the feature prefix and be scoped to a task:

```
001-document-classification-service-<short-description>

Examples:
  001-document-classification-service-api-auth
  001-document-classification-service-ingestion-worker
  001-document-classification-service-db-models
```

Never commit directly to `main`. All changes enter through pull requests.

---

## Commit Style

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add batch list endpoint
fix: handle TIFF magic byte check for big-endian files
test: add golden replay coverage for invoice class
docs: update runbook with Vault seed steps
chore: pin torch to 2.3.0
```

---

## Python Standards

### Naming Conventions

| Kind | Convention | Example |
|---|---|---|
| Modules and functions | `snake_case` | `get_by_id`, `audit_log` |
| Classes | `PascalCase` | `BatchRepository`, `IngestionService` |
| Constants | `UPPER_SNAKE_CASE` | `REVIEW_CONFIDENCE_THRESHOLD` |
| Private helpers | Leading `_` only when truly internal | `_require_admin` |

### Docstrings

Public modules, classes, and non-trivial functions use Google-style docstrings:

```python
def relabel(self, prediction_id: uuid.UUID, review_label: str) -> Prediction:
    """Apply a reviewer label to an eligible prediction.

    Args:
        prediction_id: The prediction to relabel.
        review_label: The reviewer's chosen RVL-CDIP class.

    Returns:
        The updated Prediction record.

    Raises:
        PredictionNotFound: If no prediction exists with that ID.
        ReviewNotEligible: If top1_confidence >= 0.7.
    """
```

### Error Handling

- No bare `except` blocks — always catch a specific exception type
- Re-raise with context when wrapping lower-level errors
- User-facing error messages must never include stack traces, file paths,
  credentials, or infrastructure secrets

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/ARCH.md](docs/ARCH.md) | Module boundaries, data flow diagrams, design decisions |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Architecture decision record (ADR) log |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | Day-to-day operations, testing, seeding, troubleshooting |
| [docs/SECURITY.md](docs/SECURITY.md) | Vault secrets map, bootstrap, dev vs production guidance |
| [docs/demo-checklist.md](docs/demo-checklist.md) | Step-by-step demo walkthrough with talking points |
| [docs/COLLABORATION.md](docs/COLLABORATION.md) | Team collaboration and workflow guide |
| [docs/end-to-end-flow.md](docs/end-to-end-flow.md) | Full end-to-end flow explanation and architecture diagram |

---

## Team

| Member | Workstream |
|---|---|
| Member 1 | API / Auth / RBAC |
| Member 2 | Services / Repositories / Database |
| Member 3 | Infra / SFTP / MinIO / Vault / Compose |
| Member 4 | Classifier / Workers / Cache / CI |
