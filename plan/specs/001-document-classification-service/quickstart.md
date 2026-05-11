# Quickstart: Internal Document Classification Service

This quickstart defines the expected local workflow for the planned implementation. It is not an implementation script.

## Prerequisites

- Docker and docker-compose available locally
- Python project tooling installed for tests and local commands
- `classifier.pt`, `model_card.json`, and golden-set fixtures present in the repository
- Local ports needed by the API, Postgres, Redis, MinIO, SFTP, and Vault are available

## Start Local Services

```bash
docker-compose up --build
```

Expected services:

- API service
- ingestion worker
- inference worker
- Postgres
- Redis
- MinIO
- Vault
- SFTP server

## Prepare the System

```bash
alembic upgrade head
```

Expected result: database schema exists for users, roles, batches, documents, jobs, predictions, overlays, model metadata, and audit events.

## Seed or Create Access

1. Create an initial admin through the documented local bootstrap path.
2. Sign in as admin.
3. Invite reviewer and auditor users.
4. Assign `reviewer` and `auditor` roles.

Expected result: admin can manage users and roles; reviewer and auditor can authenticate with scoped permissions.

## Ingest a Document

1. Copy a representative grayscale TIFF into the configured SFTP drop folder.
2. Wait for the ingestion worker to detect a stable file.
3. Confirm the original document appears in MinIO.
4. Confirm a classification job is queued.
5. Wait for the inference worker to process the job.

Expected result: the document appears in a batch with prediction class, confidence, model identity, status, and overlay PNG location.

## Review a Low-Confidence Prediction

1. Sign in as a reviewer.
2. Open a batch containing a prediction below 0.7 top-1 confidence.
3. Inspect the prediction and overlay.
4. Submit a replacement RVL-CDIP class.

Expected result: the corrected label is recorded, the original model prediction is preserved, affected cache entries are invalidated, and an audit event is created.

## Verify Auditor Access

1. Sign in as an auditor.
2. View batches and audit log entries.
3. Attempt to relabel a prediction.

Expected result: read operations succeed; write operation is denied and audited.

## Run Verification

```bash
pytest
pytest tests/golden
```

Expected result: unit, contract, integration, and golden-set replay tests pass. The golden-set replay reports pass/fail outcomes for expected classifier behavior.
