# Feature Specification: Internal Document Classification Service

**Feature Branch**: `001-document-classification-service`  
**Created**: 2026-05-11  
**Status**: Draft  
**Input**: User description: "Create only the specification for this project. Do not implement code yet. Build an internal document classification service for the Week 6 project. The system runs locally with docker-compose. A scanner vendor drops grayscale TIFF document images into an SFTP folder. An ingestion worker detects new files, uploads them to MinIO blob storage, and enqueues classification jobs using Redis Queue. An inference worker consumes jobs, loads a pretrained visual document classifier, classifies each document into one of the RVL-CDIP 16 layout classes, writes prediction records to Postgres, writes annotated overlay PNGs to MinIO, and invalidates affected caches. Authenticated users access the system through a FastAPI API. The API does not run inference. It exposes authentication, role-based permissions, batch listing, prediction review, audit log access, and role management. Roles: admin, reviewer, auditor. Architecture rules and deliverables as provided."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingest and Classify Vendor Documents (Priority: P1)

A scanner vendor places grayscale TIFF document images into the local SFTP drop folder. The system detects new files, stores originals durably, queues each document for classification, classifies each document into one RVL-CDIP layout class, records the prediction, stores an annotated overlay image, and makes the result available for review through the authenticated API.

**Why this priority**: This is the core value of the project. Without reliable ingestion, storage, classification, and prediction persistence, no user workflow can operate.

**Independent Test**: Can be tested by placing a representative TIFF file in the SFTP drop folder and confirming that the original image, prediction record, overlay image, job status, and cache invalidation outcome are all visible through system records and API responses.

**Acceptance Scenarios**:

1. **Given** a valid grayscale TIFF appears in the SFTP drop folder, **When** the ingestion worker detects it, **Then** the system stores the original document in blob storage, associates it with a batch, and creates a classification job.
2. **Given** a queued classification job for a stored document, **When** the inference worker processes the job, **Then** the system records exactly one top predicted RVL-CDIP class, confidence scores sufficient for review decisions, the model identity used, processing status, and the overlay image location.
3. **Given** a document has been classified, **When** cached batch or prediction views include that document, **Then** affected cached results are invalidated so users see current prediction data.

---

### User Story 2 - Review Low-Confidence Predictions (Priority: P2)

A reviewer signs in, views document batches, filters or identifies predictions whose top-1 confidence is below 0.7, inspects the prediction and overlay, and relabels predictions that need correction.

**Why this priority**: Human review is required to make low-confidence classifications usable and auditable.

**Independent Test**: Can be tested by seeding or producing a prediction below the confidence threshold, signing in as a reviewer, changing the label, and confirming the corrected label and audit history are visible while high-confidence predictions remain protected from reviewer relabeling.

**Acceptance Scenarios**:

1. **Given** a reviewer is authenticated and a batch contains predictions below 0.7 top-1 confidence, **When** the reviewer requests the batch, **Then** the system clearly identifies those predictions as reviewable.
2. **Given** a reviewer opens a reviewable prediction, **When** the reviewer submits a valid replacement RVL-CDIP class, **Then** the system records the reviewer label, preserves the original model prediction, updates affected views, and creates an audit event.
3. **Given** a reviewer attempts to relabel a prediction with top-1 confidence of 0.7 or higher, **When** the request is submitted, **Then** the system rejects the relabel request and records no label change.

---

### User Story 3 - Administer Users, Roles, and Audit Access (Priority: P3)

An admin invites users, assigns or toggles roles, and reviews audit log entries for authentication, authorization, ingestion, prediction review, and role-management events.

**Why this priority**: The service is internal but still requires controlled access, accountability, and separation of duties.

**Independent Test**: Can be tested by signing in as an admin, inviting a user, assigning roles, verifying role-specific permissions, and viewing audit entries for the administrative changes.

**Acceptance Scenarios**:

1. **Given** an admin is authenticated, **When** the admin invites a new user, **Then** the system creates an invitation path and records an audit event.
2. **Given** an admin changes a user's roles, **When** the user next accesses the system, **Then** permissions reflect the current role assignments and the role change appears in the audit log.
3. **Given** a non-admin attempts to manage roles, **When** the request is submitted, **Then** the system denies the action and records the authorization failure.

---

### User Story 4 - Audit Read-Only Activity (Priority: P4)

An auditor signs in, views batches and prediction details without making changes, and reads audit log entries needed to verify system activity and review decisions.

**Why this priority**: Read-only oversight supports internal governance without expanding write permissions.

**Independent Test**: Can be tested by signing in as an auditor, reading batch and audit data, and confirming all write attempts are rejected.

**Acceptance Scenarios**:

1. **Given** an auditor is authenticated, **When** the auditor requests batch, prediction, or audit-log information, **Then** the system returns read-only information allowed for the auditor role.
2. **Given** an auditor attempts to relabel a prediction or change roles, **When** the request is submitted, **Then** the system denies the action and records the authorization failure.

### Edge Cases

- Duplicate files from the SFTP source must not create duplicate active predictions for the same source document unless explicitly treated as a new document version.
- Unsupported, corrupted, unreadable, or non-TIFF files in the SFTP folder must be marked as failed with enough diagnostic information for operators while allowing the rest of the batch to continue.
- Ingestion must handle a file that is still being written by the scanner vendor without storing a partial document as final.
- Failed uploads, queue failures, classification failures, database write failures, and overlay write failures must leave the document in a retryable or terminal failure state that is visible to operators.
- Classification jobs retried after worker interruption must not create conflicting prediction records.
- Users with multiple roles must receive the union of allowed read permissions, while write actions remain limited to explicitly authorized role capabilities.
- Audit log reads must remain available to admins and auditors even when a prediction cannot be modified.
- Cache invalidation failures must not hide persisted prediction or review changes from subsequent direct reads.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST run as a local multi-service environment suitable for the Week 6 project using the named runtime services and project deliverables.
- **FR-002**: System MUST monitor an SFTP drop location for vendor-supplied grayscale TIFF document images.
- **FR-003**: System MUST store each accepted original document image in blob storage before classification is attempted.
- **FR-004**: System MUST group ingested documents into batches that can be listed and inspected by authorized users.
- **FR-005**: System MUST enqueue a classification job for each accepted document after successful original-image storage.
- **FR-006**: System MUST process classification jobs outside the HTTP API request path.
- **FR-007**: System MUST load and use the provided pretrained visual document classifier and accompanying model metadata for inference.
- **FR-008**: System MUST classify each processed document into exactly one of the 16 RVL-CDIP layout classes.
- **FR-009**: System MUST persist prediction records containing document identity, batch identity, predicted class, top-1 confidence, review eligibility, processing status, model identity, timestamps, and relevant storage locations.
- **FR-010**: System MUST create and store an annotated overlay PNG for each successfully classified document.
- **FR-011**: System MUST invalidate affected cached batch and prediction views after ingestion, classification, relabeling, or role changes that affect visible data.
- **FR-012**: System MUST expose authenticated HTTP access for user authentication, role-based permissions, batch listing, prediction review, audit log access, and role management.
- **FR-013**: System MUST ensure the HTTP API never performs model inference directly.
- **FR-014**: System MUST enforce these role permissions: admins can invite users, toggle roles, and view audit logs; reviewers can view batches and relabel predictions where top-1 confidence is below 0.7; auditors can read batches and audit logs only.
- **FR-015**: System MUST preserve the original model prediction when a reviewer relabels a prediction.
- **FR-016**: System MUST reject reviewer relabel attempts for predictions whose top-1 confidence is 0.7 or higher.
- **FR-017**: System MUST record audit events for authentication events, authorization failures, document ingestion outcomes, classification outcomes, relabel actions, role changes, and audit-log access.
- **FR-018**: System MUST provide role-management behavior that prevents non-admin users from inviting users or changing roles.
- **FR-019**: System MUST provide database migration support for all persistent records used by the service.
- **FR-020**: System MUST include a golden-set replay capability that verifies classifier behavior against a known set of expected document classifications.
- **FR-021**: System MUST include project documentation covering architecture, decisions, local run operations, security expectations, and collaboration practices.
- **FR-022**: System MUST include automated verification in continuous integration for tests and project quality checks.
- **FR-023**: System MUST follow the required ownership boundaries: HTTP routers only in `app/api`; business logic, transactions, and cache invalidation in `app/services`; SQL only in `app/repositories`; domain models in `app/domain`; infrastructure adapters in `app/infra`; ORM models in `app/db/models.py`; classifier loading, validation, preprocessing, inference, and golden-set replay in `app/classifier`.
- **FR-024**: System MUST deliver the named project assets: FastAPI service, Postgres persistence, Alembic migrations, Redis, RQ, MinIO, Vault, SFTP integration, fastapi-users authentication, Casbin authorization, fastapi-cache2 caching, `classifier.pt`, `model_card.json`, golden-set test, CI, `docker-compose`, `ARCH.md`, `DECISIONS.md`, `RUNBOOK.md`, `SECURITY.md`, and `COLLABORATION.md`.

### Key Entities

- **User**: An authenticated internal account with identity, status, credentials or invitation state, assigned roles, and audit-relevant timestamps.
- **Role Assignment**: The association between a user and one or more roles: admin, reviewer, and auditor.
- **Batch**: A group of ingested documents derived from vendor drop activity and used for listing, review, and audit context.
- **Document**: An individual source TIFF file with vendor/source metadata, blob-storage location, ingestion status, checksum or duplicate-detection identity, and associated prediction state.
- **Classification Job**: A queued unit of work representing a document awaiting or undergoing inference, with status, retry, failure, and timing information.
- **Prediction**: The model output for a document, including RVL-CDIP class, confidence, model metadata, review eligibility, overlay location, and reviewer correction if present.
- **Overlay Asset**: The annotated PNG generated for a classified document and stored for reviewer inspection.
- **Audit Event**: An immutable record of security-relevant, operational, and review actions, including actor, action, target, timestamp, and outcome.
- **Model Metadata**: The model card and version identity needed to interpret predictions and golden-set replay outcomes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A valid TIFF dropped into the SFTP folder becomes visible as a classified document with original storage, prediction record, and overlay asset within 2 minutes in a normal local development run.
- **SC-002**: 100% of successfully classified documents receive exactly one RVL-CDIP top prediction and an associated confidence value.
- **SC-003**: 100% of predictions with top-1 confidence below 0.7 are identifiable as reviewable to users with reviewer permission.
- **SC-004**: Reviewers can complete a relabel action for a reviewable prediction in under 60 seconds after opening the prediction detail.
- **SC-005**: 100% of denied write attempts by unauthorized roles leave prediction and role data unchanged and produce an audit event.
- **SC-006**: Admin, reviewer, and auditor role permissions are enforced correctly across all protected actions in automated acceptance tests.
- **SC-007**: Golden-set replay completes in CI and reports pass/fail results for the expected classifier outputs.
- **SC-008**: A new contributor can start the local system and execute the documented verification workflow using the project runbook in under 30 minutes on a prepared machine.

## Assumptions

- The service is intended for internal Week 6 project use and local development demonstration, not production internet exposure.
- The scanner vendor provides grayscale TIFF files through the configured SFTP drop location.
- The confidence threshold for reviewer relabel eligibility is fixed at top-1 confidence below 0.7 for this feature.
- The RVL-CDIP class list is the standard 16-class layout taxonomy associated with the pretrained model.
- The pretrained classifier file, model card, and golden-set materials are supplied as project assets or fixtures and are not trained as part of this feature.
- Email delivery or external identity-provider integration is not required beyond the local invitation and authentication behavior needed for the project.
- Audit events are retained for the life of the local project database unless explicitly cleared by local environment reset.
- This specification defines scope and acceptance expectations only; implementation tasks and code changes will be handled in later phases.
