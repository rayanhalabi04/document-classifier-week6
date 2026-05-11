<!--
Sync Impact Report
Version change: placeholder -> 1.0.0
Modified principles:
- Placeholder principle 1 -> I. Local-First Reproducibility
- Placeholder principle 2 -> II. Strict Architecture Boundaries
- Placeholder principle 3 -> III. Async Inference Separation
- Placeholder principle 4 -> IV. Auditable Security and RBAC
- Placeholder principle 5 -> V. Testable Delivery and Documentation
Added sections:
- Technical Constraints
- Development Workflow and Quality Gates
Removed sections:
- Placeholder SECTION_2_NAME
- Placeholder SECTION_3_NAME
Templates requiring updates:
- ✅ .specify/templates/plan-template.md
- ✅ .specify/templates/spec-template.md
- ✅ .specify/templates/tasks-template.md
- ✅ .specify/templates/commands/*.md not present in this project
Follow-up TODOs:
- None
-->
# Document Classifier Week 6 Constitution

## Core Principles

### I. Local-First Reproducibility

The system MUST run locally through Docker Compose with documented startup,
shutdown, migration, seeding, and verification commands. Required local services
MUST include the API, ingestion worker, inference worker, Postgres, Redis, MinIO,
Vault dev mode, and SFTP simulation. Any feature that depends on an external
service MUST provide a local adapter, fixture, or documented mock path before it
is accepted.

Rationale: the Week 6 project must be demonstrable, reviewable, and recoverable
on a prepared local machine without hidden infrastructure.

### II. Strict Architecture Boundaries

Application code MUST preserve the ownership boundaries defined by the project:
`app/api` contains HTTP routers only; `app/services` owns business logic,
transactions, and cache invalidation; `app/repositories` owns SQL only;
`app/domain` owns Pydantic domain models and enums; `app/infra` owns adapters
for Redis, MinIO, SFTP, Vault, queue, cache, and authorization infrastructure;
`app/db/models.py` owns SQLAlchemy ORM models; `app/classifier` owns model
loading, validation, preprocessing, inference, overlays, and golden-set replay.

Rationale: clear boundaries make the service teachable, testable, and safe for
parallel team implementation.

### III. Async Inference Separation

The API MUST NOT run model inference or directly process scanner uploads.
Document ingestion MUST happen through the SFTP ingestion worker, and
classification MUST happen through queued RQ inference jobs. Original documents
MUST be stored before jobs are queued, and prediction writes MUST preserve
enough state for retries, failure diagnosis, and cache invalidation.

Rationale: inference is expensive and failure-prone; isolating it from HTTP
requests keeps user workflows predictable and worker failures recoverable.

### IV. Auditable Security and RBAC

All user-facing operations MUST be authenticated unless explicitly designated as
health checks. Authorization MUST enforce the admin, reviewer, and auditor roles
through policy, not ad hoc router logic. Security-relevant events MUST be
audited, including authentication activity, authorization denials, ingestion
outcomes, classification outcomes, relabel actions, role changes, and audit-log
access.

Rationale: the project is internal, but role boundaries and auditability are
required for trustworthy review and administration.

### V. Testable Delivery and Documentation

Every implemented feature MUST include tests appropriate to its risk: unit tests
for domain and validation rules, repository tests for SQL behavior, service tests
for transactions and cache invalidation, contract tests for API behavior,
integration tests for service interactions, and golden-set tests for classifier
behavior. Documentation MUST remain current for architecture, decisions,
runbook, security, and collaboration practices.

Rationale: the system spans multiple services and a classifier; reliable
delivery requires executable checks and readable operational guidance.

## Technical Constraints

- Runtime language is Python 3.11.
- API framework is FastAPI.
- Persistence uses SQLAlchemy 2.x, Alembic, and Postgres 16.
- Queue and cache infrastructure use Redis 7, RQ, and fastapi-cache2 Redis
  backend.
- Binary object storage uses MinIO for original TIFFs and overlay PNGs.
- Secrets use HashiCorp Vault dev mode KV v2 for local development only.
- SFTP simulation uses Atmoz SFTP.
- Authentication uses fastapi-users with JWT.
- Authorization uses Casbin with SQLAlchemy adapter storage.
- Classifier runtime uses torchvision ConvNeXt Tiny or Small with
  `classifier.pt`, `model_card.json`, and golden-set replay.
- CI uses GitHub Actions and MUST cover tests, migrations, contracts, integration
  flows, golden-set replay, Docker Compose smoke checks, and documentation
  presence.

## Development Workflow and Quality Gates

- Specification, plan, and task artifacts MUST be created before implementation.
- Plans MUST include architecture-boundary checks, API endpoints, database
  tables, worker flows, cache invalidation, startup validation, tests, CI stages,
  and ownership guidance.
- Tasks MUST include owner suggestions, likely affected files, and acceptance
  criteria when requested for team coordination.
- Any change that crosses module boundaries MUST explain why in `DECISIONS.md`.
- A story or workstream is not complete until its acceptance criteria are covered
  by tests or an explicitly documented manual verification step.
- Local readiness MUST fail fast when required dependencies, secrets, buckets,
  migrations, classifier assets, or label metadata are invalid.

## Governance

This constitution supersedes conflicting project conventions. Pull requests and
task reviews MUST check compliance with the core principles, technical
constraints, and quality gates. Amendments require updating this file, adding a
Sync Impact Report, updating affected templates or guidance, and documenting any
material decision in `DECISIONS.md`.

Versioning follows semantic versioning:

- MAJOR: incompatible changes to principles, required architecture, or governance.
- MINOR: new principles, new required sections, or materially expanded gates.
- PATCH: clarifications, wording improvements, or non-semantic corrections.

Compliance exceptions MUST be documented in the implementation plan's Complexity
Tracking section with the reason, rejected simpler alternative, and mitigation.

**Version**: 1.0.0 | **Ratified**: 2026-05-11 | **Last Amended**: 2026-05-11
