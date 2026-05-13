"""Ingestion service — coordinates SFTP → MinIO → Postgres → RQ pipeline.

Transaction boundary: this service owns the commit. Object storage upload
must succeed before the document is marked stored and the RQ job is enqueued.
Cache invalidation runs after a successful commit.
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import (
    Batch,
    BatchStatus,
    ClassificationJob,
    Document,
    IngestionStatus,
    JobStatus,
)
from app.domain.errors import (
    DuplicateDocumentError,
    StorageError,
    UnsupportedFileTypeError,
)
from app.repositories.batches import BatchRepository
from app.repositories.documents import DocumentRepository
from app.repositories.jobs import ClassificationJobRepository
from app.services.audit_log import AuditLogService
from app.services.cache_invalidation import invalidate_batch_list

logger = logging.getLogger(__name__)

SUPPORTED_MIME_TYPE = "image/tiff"


def _compute_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class IngestionService:
    """Orchestrates the full ingestion flow for a single TIFF file."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._batches = BatchRepository(session)
        self._documents = DocumentRepository(session)
        self._jobs = ClassificationJobRepository(session)
        self._audit = AuditLogService(session)

    def ingest_file(
        self,
        source_path: str,
        source_filename: str,
        file_data: bytes,
        model_metadata_id: uuid.UUID,
        request_id: str | None = None,
    ) -> Document:
        """Ingest one TIFF file from the SFTP drop directory.

        Args:
            source_path: Full SFTP path of the file.
            source_filename: Bare filename (used for display and dedup).
            file_data: Raw bytes of the TIFF file.
            model_metadata_id: Active classifier metadata to associate the job with.
            request_id: Worker job ID for audit traceability.

        Returns:
            The created Document record (status = queued).

        Raises:
            UnsupportedFileTypeError: If the file is not a valid TIFF.
            DuplicateDocumentError: If an active document with the same identity exists.
            StorageError: If the MinIO upload fails.
        """
        self._validate_tiff(file_data, source_filename)

        checksum = _compute_checksum(file_data)

        existing = self._documents.find_active_duplicate(checksum, source_path)
        if existing is not None:
            raise DuplicateDocumentError(
                f"Document already active: {source_path} ({checksum[:12]}...)"
            )

        batch = self._get_or_create_batch(source_path)

        document = Document(
            id=uuid.uuid4(),
            batch_id=batch.id,
            source_path=source_path,
            source_filename=source_filename,
            source_size_bytes=len(file_data),
            source_checksum=checksum,
            mime_type=SUPPORTED_MIME_TYPE,
            ingestion_status=IngestionStatus.pending,
        )
        self._documents.create(document)

        blob_bucket, blob_key = self._upload_to_storage(document.id, file_data)
        document.blob_bucket = blob_bucket
        document.blob_key = blob_key
        document.ingestion_status = IngestionStatus.stored

        rq_job_id = self._enqueue_classification(document.id, model_metadata_id)

        job = ClassificationJob(
            id=uuid.uuid4(),
            document_id=document.id,
            rq_job_id=rq_job_id,
            status=JobStatus.queued,
            attempt_count=1,
            enqueued_at=datetime.now(timezone.utc),
        )
        self._jobs.create(job)

        document.ingestion_status = IngestionStatus.queued
        batch.document_count = (batch.document_count or 0) + 1

        self._audit.record(
            action="document.ingested",
            outcome="success",
            target_type="document",
            target_id=str(document.id),
            details={"source_path": source_path, "rq_job_id": rq_job_id},
            request_id=request_id,
        )

        self._session.commit()

        try:
            invalidate_batch_list()
        except Exception:
            logger.warning(
                "Cache invalidation failed after ingestion of %s", document.id
            )

        return document

    def mark_failed(
        self,
        source_path: str,
        source_filename: str,
        reason: str,
        request_id: str | None = None,
    ) -> None:
        """Record a failed ingestion attempt without creating a document record."""
        self._audit.record(
            action="document.ingestion_failed",
            outcome="failure",
            target_type="document",
            target_id=source_path,
            details={"source_filename": source_filename, "reason": reason},
            request_id=request_id,
        )
        self._session.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_tiff(self, data: bytes, filename: str) -> None:
        """Reject files that are not TIFFs by checking the magic bytes."""
        tiff_magic = (b"II*\x00", b"MM\x00*")  # little-endian, big-endian TIFF
        if not any(data.startswith(magic) for magic in tiff_magic):
            raise UnsupportedFileTypeError(
                f"File '{filename}' is not a valid TIFF (magic bytes mismatch)."
            )

    def _get_or_create_batch(self, source_path: str) -> Batch:
        """Create a fresh batch for each ingested file.

        Previous behaviour reused any open `processing` batch indefinitely
        because nothing in the system transitions a batch to `completed`,
        so every document piled into a single row and `document_count` grew
        forever. One batch per file is the simplest correct behaviour and
        gives the API and reviewers a clean unit to track.
        """
        import os

        source_dir = os.path.dirname(source_path) or "/"
        batch = Batch(
            id=uuid.uuid4(),
            source=source_dir,
            status=BatchStatus.processing,
            document_count=0,
            reviewable_count=0,
        )
        return self._batches.create(batch)

    def _upload_to_storage(
        self, document_id: uuid.UUID, data: bytes
    ) -> tuple[str, str]:
        """Upload TIFF bytes to MinIO and return (bucket, key)."""
        try:
            from app.infra.minio import upload_original

            return upload_original(document_id, data)
        except Exception as exc:
            raise StorageError(
                f"MinIO upload failed for document {document_id}"
            ) from exc

    def _enqueue_classification(
        self, document_id: uuid.UUID, model_metadata_id: uuid.UUID
    ) -> str:
        """Enqueue an RQ classification job and return the RQ job ID."""
        from app.infra.queue import enqueue_classification_job

        return enqueue_classification_job(document_id, model_metadata_id)
