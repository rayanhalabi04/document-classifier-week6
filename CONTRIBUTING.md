# Contributing Guide

## Branch Naming

All branches must follow this pattern:

```
001-document-classification-service-<short-description>
```

Examples:
```
001-document-classification-service-api-auth
001-document-classification-service-ingestion-worker
001-document-classification-service-db-migrations
```

Direct commits to `main` are not allowed. All work enters through pull requests.

---

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <short description>

Types:
  feat      New feature or behavior
  fix       Bug fix
  test      Test additions or changes
  docs      Documentation only
  chore     Tooling, deps, config (no production code change)
  refactor  Code change that neither fixes a bug nor adds a feature
```

Examples:
```
feat: add batch list endpoint with role-scoped filtering
fix: reject TIFF files with big-endian magic bytes
test: add repository test for duplicate document detection
docs: update runbook with Vault seed instructions
chore: pin sqlalchemy to 2.0.30
```

---

## Pull Request Requirements

Use the PR template at `.github/pull_request_template.md`. Every PR must include:

- **Summary** — what changed and why
- **Linked task** — Trello card ID or task number from tasks.md (e.g. T019)
- **Files changed** — brief list of affected modules
- **Test evidence** — paste the pytest output or CI link
- **Security impact** — note any auth, secrets, or audit changes; write "None" if not applicable
- **Screenshots or logs** — for API or worker behavior changes

### Review Rules

- Every PR requires at least one reviewer who does not own the primary workstream
- Changes that cross workstream boundaries require review from the owner of the affected workstream
- PRs must not be merged while CI is failing

---

## Python Naming Conventions

| Kind | Convention | Example |
|---|---|---|
| Modules and functions | `snake_case` | `get_by_id`, `audit_log` |
| Classes | `PascalCase` | `BatchRepository`, `IngestionService` |
| Constants | `UPPER_SNAKE_CASE` | `REVIEW_CONFIDENCE_THRESHOLD`, `VALID_ROLES` |
| Private helpers | Leading `_` only when truly internal | `_require_admin`, `_validate_role` |

---

## Docstring Standard (Google Style)

Public modules, classes, and non-trivial functions must include Google-style docstrings:

```python
def assign_role(
    self,
    target_user_id: uuid.UUID,
    role: str,
    acting_admin_id: uuid.UUID,
) -> RoleAssignment | None:
    """Assign a role to a user. No-op if the role is already active.

    Args:
        target_user_id: User receiving the role.
        role: One of admin, reviewer, auditor.
        acting_admin_id: Admin performing the action (for audit).

    Returns:
        The new RoleAssignment, or None if already active.

    Raises:
        PermissionDenied: If acting user is not an admin.
        ValueError: If role is not a valid role name.
    """
```

Docstrings must explain **purpose, arguments, returns, raises, and side effects**.
Do not describe what the code does — describe why and what callers need to know.

---

## Error Handling Rules

- No bare `except` blocks — always catch a specific exception type
- When wrapping a lower-level error, re-raise with context:

```python
# Good
try:
    upload_original(document_id, data)
except MinioException as exc:
    raise StorageError(f"Upload failed for document {document_id}") from exc

# Bad
try:
    upload_original(document_id, data)
except:
    pass
```

- User-facing error responses must never include stack traces, file paths,
  credentials, internal IDs beyond what was requested, or infrastructure secrets

---

## Code Quality — Running Checks Locally

Before opening a PR, run all checks from the `backend/` directory:

```bash
# Format code
black .

# Sort imports
isort .

# Lint
flake8 .

# Type check
mypy app/

# Run tests with coverage
pytest

# Run all checks in one line (mirrors CI)
black --check . && isort --check-only . && flake8 . && mypy app/ && pytest
```

CI will fail if any of these fail. Fix locally before pushing.

---

## Test Requirements

- New behavior must have tests at the lowest useful level
- Use Arrange-Act-Assert structure
- Happy path, permission denials, and failure states must all be covered
- Include the test command and output summary in your PR description

```
# Example PR test evidence:
$ pytest tests/service/test_prediction_review.py -v
PASSED tests/service/test_prediction_review.py::test_relabel_success
PASSED tests/service/test_prediction_review.py::test_relabel_rejects_high_confidence
PASSED tests/service/test_prediction_review.py::test_relabel_invalid_label
3 passed in 0.42s
```

---

## Secret Hygiene

- Never commit `.env` files, tokens, passwords, or credentials
- Use Vault for all local secrets (see [docs/RUNBOOK.md](docs/RUNBOOK.md))
- If you accidentally commit a secret, rotate it immediately and notify the team
- CI runs secret scanning — commits with detected secrets will be blocked
