"""Classification job service — manages RQ job lifecycle in Postgres.

Services own the transaction. Repositories own SQL. Workers call this service
to transition job state; the API never modifies jobs directly.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import ClassificationJob, JobStatus, OverlayAsset, Prediction
from app.domain.errors import ClassificationError
from app.repositories.jobs import ClassificationJobRepository
from app.repositories.predictions import PredictionRepository
from app.services.audit_log import AuditLogService
from app.services.cache_invalidation import invalidate_after_classification

logger = logging.getLogger(__name__)

REVIEW_CONFIDENCE_THRESHOLD = 0.7


class ClassificationJobService:
    """Manages RQ job state transitions and persists inference results."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._jobs = ClassificationJobRepository(session)
        self._predictions = PredictionRepository(session)
        self._audit = AuditLogService(session)

    def mark_running(self, job_id: uuid.UUID) -> ClassificationJob:
        """Transition a queued job to running state."""
        job = self._require_job(job_id)
        job.status = JobStatus.running
        job.started_at = datetime.now(timezone.utc)
        self._jobs.update(job)
        self._session.commit()
        return job

    def persist_result(
        self,
        job_id: uuid.UUID,
        document_id: uuid.UUID,
        model_metadata_id: uuid.UUID,
        predicted_class: str,
        top1_confidence: float,
        class_scores: dict[str, float],
        blob_bucket: str,
        blob_key: str,
        batch_id: uuid.UUID,
    ) -> Prediction:
        """Persist a successful inference result and overlay asset in one transaction.

        Args:
            job_id: The classification job being completed.
            document_id: Document that was classified.
            model_metadata_id: Model version that produced the result.
            predicted_class: Top-1 RVL-CDIP class label.
            top1_confidence: Confidence score for the top-1 class (0.0–1.0).
            class_scores: Full 16-class score mapping.
            blob_bucket: MinIO bucket where the overlay PNG was stored.
            blob_key: MinIO key for the overlay PNG.
            batch_id: Parent batch (used for cache invalidation).

        Returns:
            The created Prediction record.
        """
        review_eligible = top1_confidence < REVIEW_CONFIDENCE_THRESHOLD

        prediction = Prediction(
            id=uuid.uuid4(),
            document_id=document_id,
            model_metadata_id=model_metadata_id,
            predicted_class=predicted_class,
            top1_confidence=top1_confidence,
            class_scores_json=class_scores,
            review_eligible=review_eligible,
        )
        self._predictions.create(prediction)

        overlay = OverlayAsset(
            id=uuid.uuid4(),
            prediction_id=prediction.id,
            blob_bucket=blob_bucket,
            blob_key=blob_key,
            content_type="image/png",
        )
        self._predictions.create_overlay(overlay)

        job = self._require_job(job_id)
        job.status = JobStatus.succeeded
        job.finished_at = datetime.now(timezone.utc)
        self._jobs.update(job)

        self._audit.record(
            action="document.classified",
            outcome="success",
            target_type="prediction",
            target_id=str(prediction.id),
            details={
                "document_id": str(document_id),
                "predicted_class": predicted_class,
                "top1_confidence": top1_confidence,
                "review_eligible": review_eligible,
            },
        )

        self._session.commit()

        try:
            invalidate_after_classification(batch_id, prediction.id)
        except Exception:
            logger.warning(
                "Cache invalidation failed after classification of document %s", document_id
            )

        return prediction

    def mark_retryable_failure(
        self, job_id: uuid.UUID, error: str
    ) -> ClassificationJob:
        """Record a retryable failure — the job can be requeued."""
        job = self._require_job(job_id)
        job.status = JobStatus.retryable_failed
        job.last_error = error
        job.finished_at = datetime.now(timezone.utc)
        self._jobs.update(job)
        self._audit.record(
            action="document.classification_failed",
            outcome="failure",
            target_type="classification_job",
            target_id=str(job_id),
            details={"error": error, "retryable": True},
        )
        self._session.commit()
        return job

    def mark_terminal_failure(
        self, job_id: uuid.UUID, error: str
    ) -> ClassificationJob:
        """Record a terminal failure — the job will not be retried."""
        job = self._require_job(job_id)
        job.status = JobStatus.terminal_failed
        job.last_error = error
        job.finished_at = datetime.now(timezone.utc)
        self._jobs.update(job)
        self._audit.record(
            action="document.classification_failed",
            outcome="failure",
            target_type="classification_job",
            target_id=str(job_id),
            details={"error": error, "retryable": False},
        )
        self._session.commit()
        return job

    # ------------------------------------------------------------------

    def _require_job(self, job_id: uuid.UUID) -> ClassificationJob:
        job = self._jobs.get_by_id(job_id)
        if job is None:
            raise ClassificationError(f"Classification job {job_id} not found.")
        return job
