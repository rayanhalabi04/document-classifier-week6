# Member 1 Completed Tasks

## Summary

Member 1 completed the main API/auth/RBAC foundation for the Week 6 Document Classifier service. The completed work includes FastAPI app creation and router registration, fastapi-users JWT wiring, role and permission constants, baseline Casbin RBAC policies, authorization dependencies, and startup validation for persisted RBAC policy state. Member 1 also completed several team workflow documents around ownership, Trello structure, PR requirements, and contribution rules.

## Completed Tasks

### T007 — Define FastAPI application and router registration plan
**Status:** Done

**What was implemented:**
- Created the FastAPI app factory with project title, version, description, and lifespan startup hook.
- Registered the health, auth, users, roles, batches, predictions, and audit routers.
- Kept inference/classification execution endpoints out of the API surface.
- Added OpenAPI contract tests that verify expected route prefixes and confirm forbidden inference-style routes are absent.

**Evidence:**
- `backend/app/main.py`
- `backend/app/api/auth.py`
- `backend/app/api/users.py`
- `backend/app/api/roles.py`
- `backend/app/api/batches.py`
- `backend/app/api/predictions.py`
- `backend/app/api/audit.py`
- `backend/app/api/health.py`
- `backend/tests/contract/test_openapi_contract.py`

**How to verify:**
```bash
cd backend
pytest tests/contract/test_openapi_contract.py
```

**Notes for the team:**
- Some registered feature routers still contain `501 Not Implemented` placeholders. This task is complete for app creation, router registration, and OpenAPI exposure only.

### T008 — Define fastapi-users JWT authentication setup
**Status:** Done

**What was implemented:**
- Added fastapi-users JWT authentication wiring with bearer transport and a one-hour JWT lifetime.
- Added auth routes for registration and JWT login under `/auth`.
- Added `/users/me` current-user behavior backed by `current_active_user`.
- Integrated the `User` SQLAlchemy model with fastapi-users through `SyncUserDatabase`, `UserManager`, and `UserRepository`.
- Loaded JWT signing material from Vault through `load_jwt_secret()` and added startup validation for placeholder JWT secrets.

**Evidence:**
- `backend/app/services/auth.py`
- `backend/app/api/auth.py`
- `backend/app/api/users.py`
- `backend/app/db/models.py`
- `backend/app/repositories/users.py`
- `backend/app/services/startup_validation.py`
- `backend/tests/contract/test_auth_contract.py`

**How to verify:**
```bash
cd backend
pytest tests/contract/test_auth_contract.py
```

**Notes for the team:**
- The contract tests cover auth route registration, missing-token rejection, invalid-token rejection, and JWT secret validation behavior.

### T009 — Define Casbin role policy model and baseline policies
**Status:** Done

**What was implemented:**
- Defined role constants for `admin`, `reviewer`, and `auditor`.
- Defined permission action/resource constants used by API dependencies and services.
- Added a Casbin RBAC model using subjects, objects, actions, and role grouping.
- Added baseline policies for admin, reviewer, and auditor permissions.
- Added DB-backed Casbin enforcer helpers for loading policies, assigning roles, removing roles, checking permissions, and seeding baseline policies.
- Added startup authorization validation so the API fails if the Casbin policy table is empty or missing required baseline policies.
- Added tests for the permission matrix, denial defaults, multi-role union behavior, DB-backed enforcement, role changes without new JWTs, and startup failure when policies are missing.

**Evidence:**
- `backend/app/domain/roles.py`
- `backend/app/infra/authz/rbac_model.conf`
- `backend/app/infra/authz/casbin_enforcer.py`
- `backend/app/infra/casbin.py`
- `backend/app/services/authorization.py`
- `backend/app/api/dependencies.py`
- `backend/app/services/startup_authorization.py`
- `backend/scripts/seed_casbin_policies.py`
- `backend/tests/unit/test_permissions.py`
- `backend/tests/unit/test_casbin_authorization.py`

**How to verify:**
```bash
cd backend
pytest tests/unit/test_permissions.py tests/unit/test_casbin_authorization.py
```

**Notes for the team:**
- The implemented baseline allows admins to manage users/roles and read core resources, reviewers to read batches/predictions and relabel predictions, and auditors to read batches, predictions, and audit logs without write permissions.

### T050 — Define Trello board structure
**Status:** Done

**What was implemented:**
- Documented the team board lists: Backlog, Ready, In Progress, Review, Blocked, Done, and Demo Prep.
- Added expected card fields and movement expectations for review and completion.

**Evidence:**
- `docs/COLLABORATION.md`

**How to verify:**
```bash
sed -n '1,120p' docs/COLLABORATION.md
```

**Notes for the team:**
- The collaboration guide is under `docs/COLLABORATION.md`; the root `COLLABORATION.md` file is currently empty.

### T051 — Map workstreams to four members
**Status:** Done

**What was implemented:**
- Documented ownership for all four workstreams.
- Mapped Member 1 to API/Auth/RBAC, Member 2 to services/repositories/database, Member 3 to infra/SFTP/MinIO/Vault/Compose, and Member 4 to classifier/workers/cache/CI.
- Added cross-workstream review expectations.

**Evidence:**
- `docs/COLLABORATION.md`
- `README.md`

**How to verify:**
```bash
sed -n '1,80p' docs/COLLABORATION.md
sed -n '120,220p' README.md
```

**Notes for the team:**
- The same ownership split appears in the README team table for quick reference.

### T054 — Define CONTRIBUTING workflow for branches, commits, and pull requests
**Status:** Done

**What was implemented:**
- Documented branch naming for the `001-document-classification-service-*` pattern.
- Documented that direct commits to `main` are not allowed.
- Documented Conventional Commit message expectations.
- Documented PR requirements, review rules, required test evidence, and linked task/Trello card expectations.
- Added related repository standards for Python naming, docstrings, error handling, tests, and secret hygiene.

**Evidence:**
- `CONTRIBUTING.md`
- `README.md`

**How to verify:**
```bash
sed -n '1,180p' CONTRIBUTING.md
sed -n '70,140p' README.md
```

**Notes for the team:**
- The contribution guide is complete enough for branch, commit, PR, review, and test-evidence workflow expectations.

### T055 — Add GitHub pull request template requirements
**Status:** Done

**What was implemented:**
- Added a PR template with sections for summary, linked task/Trello card, files changed, type of change, tests/evidence, security impact, documentation impact, dependency impact, and reviewer checklist.

**Evidence:**
- `.github/pull_request_template.md`
- `CONTRIBUTING.md`

**How to verify:**
```bash
sed -n '1,120p' .github/pull_request_template.md
```

**Notes for the team:**
- The template aligns with the contribution guide's required PR evidence and review checklist.
