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
- Python 3.11
- Git

### 1. Clone and configure

```bash
git clone <repo-url>
cd document-classifier-week6
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
docker compose up -d
```

Waits for Postgres, Redis, MinIO, Vault, and SFTP to be healthy before
the API and workers start.

### 4. Run database migrations

```bash
docker compose exec api alembic upgrade head
```

### 5. Seed Vault secrets and users

```bash
docker compose exec api python scripts/seed_vault.py
docker compose exec api python scripts/seed_users.py
```

### 6. Verify everything is running

```bash
curl http://localhost:8000/health/ready
# → {"status": "ok"}
```

See [docs/RUNBOOK.md](docs/RUNBOOK.md) for the full local workflow including
dropping a TIFF, checking classification results, and running the demo.

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

## Architecture

See [docs/ARCH.md](docs/ARCH.md) for module boundaries, data flow diagrams,
and the reasoning behind key design decisions.

See [docs/DECISIONS.md](docs/DECISIONS.md) for the full architecture decision log.

---

## Team

| Member | Workstream |
|---|---|
| Member 1 | API / Auth / RBAC |
| Member 2 | Services / Repositories / Database |
| Member 3 | Infra / SFTP / MinIO / Vault / Compose |
| Member 4 | Classifier / Workers / Cache / CI |
