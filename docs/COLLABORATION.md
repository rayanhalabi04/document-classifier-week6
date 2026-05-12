# Collaboration Guide

## Team Ownership

| Member | Workstream | Key Files |
|---|---|---|
| Member 1 | API / Auth / RBAC | `app/api/`, `app/infra/casbin.py`, contract tests |
| Member 2 | Services / Repositories / Database | `app/services/`, `app/repositories/`, `app/db/` |
| Member 3 | Infra / SFTP / MinIO / Vault / Compose | `app/infra/`, `docker-compose.yml`, `Dockerfile` |
| Member 4 | Classifier / Workers / Cache / CI | `app/classifier/`, `app/workers/`, `.github/workflows/` |

Cross-cutting changes (e.g. adding a column used by two workstreams) require
review from both owners before merge.

---

## Trello Board Structure

| List | Purpose |
|---|---|
| Backlog | All planned tasks not yet started |
| Ready | Tasks unblocked and ready to pick up |
| In Progress | Actively being worked on (one card per person max) |
| Review | PR open, waiting for review |
| Blocked | Waiting on another task or decision |
| Done | Merged to main |
| Demo Prep | Items needed specifically for final presentation |

Each card must include:
- Title matching the task ID (e.g. `T019 — ingestion service`)
- Owner name
- Files likely affected
- Acceptance criteria (copied from tasks.md)
- Link to PR when open
- Test commands and results before moving to Review

---

## Integration Review Checkpoints

These checkpoints gate progress. Each one requires a sync between all
members before moving forward.

### Checkpoint 1 — Schema Freeze
**When**: Before Member 1 and Member 4 start writing services or workers.
**Gate**: `db/models.py` and `001_initial_schema.py` are merged to main.
`alembic upgrade head` succeeds against a fresh Postgres 16 container.
**Who reviews**: All four members sign off on the table names and column
contracts — changes after this point require a new migration.

### Checkpoint 2 — API Contract Freeze
**When**: Before integration tests are written.
**Gate**: All 12 API routes are registered in `app/main.py`. OpenAPI schema
generates without errors. Contract tests pass for auth, role matrix, and
no-inference rule.
**Who reviews**: Member 1 (owns routes) + Member 2 (owns services routes call).

### Checkpoint 3 — Worker End-to-End Demo
**When**: Before final presentation rehearsal.
**Gate**: Drop a TIFF into the SFTP vendor directory. Within 2 minutes,
`GET /predictions/{id}` returns a predicted class, confidence score, and
overlay URL. Overlay PNG is retrievable from MinIO.
**Who reviews**: Member 3 (ingestion) + Member 4 (inference) demonstrate
the flow live. Member 2 verifies Postgres records.

### Checkpoint 4 — Review / Admin / Auditor Demo
**When**: After Checkpoint 3.
**Gate**: Reviewer can relabel a low-confidence prediction. Admin can change
user roles. Auditor can read audit events. Non-authorized actions return 403.
**Who reviews**: Member 1 demonstrates API flows. Member 2 verifies audit
rows in Postgres.

### Checkpoint 5 — Final Presentation Readiness
**When**: 24 hours before presentation.
**Gate**: All CI stages pass on main. `docker compose up` starts cleanly.
README and RUNBOOK accurately describe local setup. Demo checklist in
RUNBOOK.md is rehearsed end-to-end.
**Who reviews**: All four members run the full demo checklist independently.

---

## Communication Norms

- Use feature branches — never commit directly to `main`
- Tag the relevant member in PR review when changes cross workstream boundaries
- If blocked for more than 2 hours, post in the team channel with the blocker
- Update the Trello card status when you start, open a PR, or get blocked
- Keep PRs focused — one task per PR where possible
