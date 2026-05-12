"""Shared fixtures for repository unit tests."""

import uuid
from unittest.mock import MagicMock

import pytest

from app.db.models import (
    AuditEvent,
    Batch,
    BatchStatus,
    ClassificationJob,
    Document,
    IngestionStatus,
    JobStatus,
    OverlayAsset,
    Prediction,
    RoleAssignment,
)


@pytest.fixture()
def mock_session():
    """Return a MagicMock that mimics a SQLAlchemy Session."""
    session = MagicMock()
    return session


@pytest.fixture()
def batch_id():
    return uuid.uuid4()


@pytest.fixture()
def document_id():
    return uuid.uuid4()


@pytest.fixture()
def job_id():
    return uuid.uuid4()


@pytest.fixture()
def prediction_id():
    return uuid.uuid4()


@pytest.fixture()
def user_id():
    return uuid.uuid4()


@pytest.fixture()
def sample_batch(batch_id):
    batch = MagicMock(spec=Batch)
    batch.id = batch_id
    batch.status = BatchStatus.processing
    batch.document_count = 0
    return batch


@pytest.fixture()
def sample_document(document_id, batch_id):
    doc = MagicMock(spec=Document)
    doc.id = document_id
    doc.batch_id = batch_id
    doc.source_checksum = "abc123"
    doc.source_path = "/vendor/test.tif"
    doc.ingestion_status = IngestionStatus.pending
    return doc


@pytest.fixture()
def sample_job(job_id, document_id):
    job = MagicMock(spec=ClassificationJob)
    job.id = job_id
    job.document_id = document_id
    job.rq_job_id = "rq-abc"
    job.status = JobStatus.queued
    return job


@pytest.fixture()
def sample_prediction(prediction_id, document_id):
    pred = MagicMock(spec=Prediction)
    pred.id = prediction_id
    pred.document_id = document_id
    pred.predicted_class = "invoice"
    pred.top1_confidence = 0.55
    pred.review_eligible = True
    return pred
