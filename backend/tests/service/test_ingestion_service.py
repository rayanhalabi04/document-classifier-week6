"""Unit tests for IngestionService."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

import app.infra.minio  # noqa: F401 — must be imported so patch() can resolve the module
import app.infra.queue  # noqa: F401 — must be imported so patch() can resolve the module
from app.db.models import Document, IngestionStatus
from app.domain.errors import (
    DuplicateDocumentError,
    StorageError,
    UnsupportedFileTypeError,
)
from app.services.ingestion import IngestionService

# Minimal valid TIFF magic bytes (little-endian)
TIFF_MAGIC = b"II*\x00" + b"\x00" * 100
NON_TIFF = b"NOTIFF" + b"\x00" * 100

MODEL_METADATA_ID = uuid.uuid4()


@pytest.fixture()
def mock_session():
    session = MagicMock()
    return session


@pytest.fixture()
def mock_batch():
    batch = MagicMock()
    batch.id = uuid.uuid4()
    batch.document_count = 0
    return batch


@pytest.fixture()
def service(mock_session, mock_batch):
    with (
        patch(
            "app.repositories.batches.BatchRepository.list", return_value=[mock_batch]
        ),
        patch(
            "app.repositories.documents.DocumentRepository.find_active_duplicate",
            return_value=None,
        ),
        patch(
            "app.repositories.documents.DocumentRepository.create",
            side_effect=lambda d: d,
        ),
        patch(
            "app.repositories.jobs.ClassificationJobRepository.create",
            side_effect=lambda j: j,
        ),
        patch(
            "app.infra.minio.upload_original",
            return_value=("originals", "docs/test.tif"),
        ),
        patch("app.infra.queue.enqueue_classification_job", return_value="rq-xyz"),
    ):
        yield IngestionService(mock_session)


class TestValidateTiff:
    def test_accepts_little_endian_tiff(self, mock_session, mock_batch):
        with (
            patch(
                "app.repositories.batches.BatchRepository.list",
                return_value=[mock_batch],
            ),
            patch(
                "app.repositories.documents.DocumentRepository.find_active_duplicate",
                return_value=None,
            ),
            patch(
                "app.repositories.documents.DocumentRepository.create",
                side_effect=lambda d: d,
            ),
            patch(
                "app.repositories.jobs.ClassificationJobRepository.create",
                side_effect=lambda j: j,
            ),
            patch(
                "app.infra.minio.upload_original",
                return_value=("originals", "docs/test.tif"),
            ),
            patch("app.infra.queue.enqueue_classification_job", return_value="rq-xyz"),
        ):
            svc = IngestionService(mock_session)
            doc = svc.ingest_file(
                source_path="/vendor/doc.tif",
                source_filename="doc.tif",
                file_data=TIFF_MAGIC,
                model_metadata_id=MODEL_METADATA_ID,
            )
            assert doc.ingestion_status == IngestionStatus.queued

    def test_accepts_big_endian_tiff(self, mock_session, mock_batch):
        big_endian = b"MM\x00*" + b"\x00" * 100
        with (
            patch(
                "app.repositories.batches.BatchRepository.list",
                return_value=[mock_batch],
            ),
            patch(
                "app.repositories.documents.DocumentRepository.find_active_duplicate",
                return_value=None,
            ),
            patch(
                "app.repositories.documents.DocumentRepository.create",
                side_effect=lambda d: d,
            ),
            patch(
                "app.repositories.jobs.ClassificationJobRepository.create",
                side_effect=lambda j: j,
            ),
            patch(
                "app.infra.minio.upload_original",
                return_value=("originals", "docs/test.tif"),
            ),
            patch("app.infra.queue.enqueue_classification_job", return_value="rq-xyz"),
        ):
            svc = IngestionService(mock_session)
            doc = svc.ingest_file(
                source_path="/vendor/doc.tif",
                source_filename="doc.tif",
                file_data=big_endian,
                model_metadata_id=MODEL_METADATA_ID,
            )
            assert doc is not None

    def test_rejects_non_tiff_file(self, mock_session):
        svc = IngestionService(mock_session)
        with pytest.raises(UnsupportedFileTypeError, match="not a valid TIFF"):
            svc.ingest_file(
                source_path="/vendor/doc.pdf",
                source_filename="doc.pdf",
                file_data=NON_TIFF,
                model_metadata_id=MODEL_METADATA_ID,
            )


class TestDuplicateDetection:
    def test_raises_on_duplicate_document(self, mock_session):
        existing = MagicMock(spec=Document)
        with patch(
            "app.repositories.documents.DocumentRepository.find_active_duplicate",
            return_value=existing,
        ):
            svc = IngestionService(mock_session)
            with pytest.raises(DuplicateDocumentError):
                svc.ingest_file(
                    source_path="/vendor/doc.tif",
                    source_filename="doc.tif",
                    file_data=TIFF_MAGIC,
                    model_metadata_id=MODEL_METADATA_ID,
                )


class TestStorageFailure:
    def test_raises_storage_error_on_minio_failure(self, mock_session, mock_batch):
        with (
            patch(
                "app.repositories.batches.BatchRepository.list",
                return_value=[mock_batch],
            ),
            patch(
                "app.repositories.documents.DocumentRepository.find_active_duplicate",
                return_value=None,
            ),
            patch(
                "app.repositories.documents.DocumentRepository.create",
                side_effect=lambda d: d,
            ),
            patch(
                "app.infra.minio.upload_original",
                side_effect=RuntimeError("connection refused"),
            ),
        ):
            svc = IngestionService(mock_session)
            with pytest.raises(StorageError, match="MinIO upload failed"):
                svc.ingest_file(
                    source_path="/vendor/doc.tif",
                    source_filename="doc.tif",
                    file_data=TIFF_MAGIC,
                    model_metadata_id=MODEL_METADATA_ID,
                )


class TestSuccessfulIngestion:
    def test_commits_after_ingestion(self, mock_session, mock_batch):
        with (
            patch(
                "app.repositories.batches.BatchRepository.list",
                return_value=[mock_batch],
            ),
            patch(
                "app.repositories.documents.DocumentRepository.find_active_duplicate",
                return_value=None,
            ),
            patch(
                "app.repositories.documents.DocumentRepository.create",
                side_effect=lambda d: d,
            ),
            patch(
                "app.repositories.jobs.ClassificationJobRepository.create",
                side_effect=lambda j: j,
            ),
            patch(
                "app.infra.minio.upload_original",
                return_value=("originals", "docs/test.tif"),
            ),
            patch("app.infra.queue.enqueue_classification_job", return_value="rq-xyz"),
            patch("app.services.cache_invalidation.invalidate_batch_list"),
        ):
            svc = IngestionService(mock_session)
            svc.ingest_file(
                source_path="/vendor/doc.tif",
                source_filename="doc.tif",
                file_data=TIFF_MAGIC,
                model_metadata_id=MODEL_METADATA_ID,
            )
            mock_session.commit.assert_called_once()

    def test_cache_failure_does_not_raise(self, mock_session, mock_batch):
        with (
            patch(
                "app.repositories.batches.BatchRepository.list",
                return_value=[mock_batch],
            ),
            patch(
                "app.repositories.documents.DocumentRepository.find_active_duplicate",
                return_value=None,
            ),
            patch(
                "app.repositories.documents.DocumentRepository.create",
                side_effect=lambda d: d,
            ),
            patch(
                "app.repositories.jobs.ClassificationJobRepository.create",
                side_effect=lambda j: j,
            ),
            patch(
                "app.infra.minio.upload_original",
                return_value=("originals", "docs/test.tif"),
            ),
            patch("app.infra.queue.enqueue_classification_job", return_value="rq-xyz"),
            patch(
                "app.services.cache_invalidation.invalidate_batch_list",
                side_effect=Exception("Redis down"),
            ),
        ):
            svc = IngestionService(mock_session)
            # Should not raise even if cache fails
            doc = svc.ingest_file(
                source_path="/vendor/doc.tif",
                source_filename="doc.tif",
                file_data=TIFF_MAGIC,
                model_metadata_id=MODEL_METADATA_ID,
            )
            assert doc is not None


class TestMarkFailed:
    def test_records_failure_and_commits(self, mock_session):
        with patch("app.repositories.audit_events.AuditEventRepository.create"):
            svc = IngestionService(mock_session)
            svc.mark_failed(
                source_path="/vendor/bad.pdf",
                source_filename="bad.pdf",
                reason="not a tiff",
            )
            mock_session.commit.assert_called_once()
