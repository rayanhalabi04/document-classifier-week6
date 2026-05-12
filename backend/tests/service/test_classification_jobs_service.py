"""Unit tests for ClassificationJobService."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.db.models import ClassificationJob, JobStatus
from app.domain.errors import ClassificationError
from app.services.classification_jobs import ClassificationJobService


@pytest.fixture()
def mock_session():
    return MagicMock()


@pytest.fixture()
def job_id():
    return uuid.uuid4()


@pytest.fixture()
def document_id():
    return uuid.uuid4()


@pytest.fixture()
def model_metadata_id():
    return uuid.uuid4()


@pytest.fixture()
def batch_id():
    return uuid.uuid4()


@pytest.fixture()
def queued_job(job_id, document_id):
    job = MagicMock(spec=ClassificationJob)
    job.id = job_id
    job.document_id = document_id
    job.status = JobStatus.queued
    return job


class TestMarkRunning:
    def test_transitions_job_to_running(self, mock_session, queued_job, job_id):
        with patch(
            "app.repositories.jobs.ClassificationJobRepository.get_by_id",
            return_value=queued_job,
        ):
            svc = ClassificationJobService(mock_session)
            result = svc.mark_running(job_id)

        assert result.status == JobStatus.running
        assert result.started_at is not None
        mock_session.commit.assert_called_once()

    def test_raises_when_job_not_found(self, mock_session, job_id):
        with patch(
            "app.repositories.jobs.ClassificationJobRepository.get_by_id",
            return_value=None,
        ):
            svc = ClassificationJobService(mock_session)
            with pytest.raises(ClassificationError):
                svc.mark_running(job_id)


class TestPersistResult:
    def test_creates_prediction_and_commits(
        self, mock_session, queued_job, job_id, document_id, model_metadata_id, batch_id
    ):
        with (
            patch(
                "app.repositories.jobs.ClassificationJobRepository.get_by_id",
                return_value=queued_job,
            ),
            patch(
                "app.repositories.predictions.PredictionRepository.create",
                side_effect=lambda p: p,
            ),
            patch(
                "app.repositories.predictions.PredictionRepository.create_overlay",
                side_effect=lambda o: o,
            ),
            patch("app.services.cache_invalidation.invalidate_after_classification"),
        ):
            svc = ClassificationJobService(mock_session)
            prediction = svc.persist_result(
                job_id=job_id,
                document_id=document_id,
                model_metadata_id=model_metadata_id,
                predicted_class="invoice",
                top1_confidence=0.55,
                class_scores={"invoice": 0.55, "letter": 0.1},
                blob_bucket="overlays",
                blob_key="overlays/test.png",
                batch_id=batch_id,
            )

        assert prediction.predicted_class == "invoice"
        assert prediction.review_eligible is True  # confidence 0.55 < 0.7
        assert queued_job.status == JobStatus.succeeded
        mock_session.commit.assert_called_once()

    def test_sets_review_eligible_false_for_high_confidence(
        self, mock_session, queued_job, job_id, document_id, model_metadata_id, batch_id
    ):
        with (
            patch(
                "app.repositories.jobs.ClassificationJobRepository.get_by_id",
                return_value=queued_job,
            ),
            patch(
                "app.repositories.predictions.PredictionRepository.create",
                side_effect=lambda p: p,
            ),
            patch(
                "app.repositories.predictions.PredictionRepository.create_overlay",
                side_effect=lambda o: o,
            ),
            patch("app.services.cache_invalidation.invalidate_after_classification"),
        ):
            svc = ClassificationJobService(mock_session)
            prediction = svc.persist_result(
                job_id=job_id,
                document_id=document_id,
                model_metadata_id=model_metadata_id,
                predicted_class="invoice",
                top1_confidence=0.95,
                class_scores={"invoice": 0.95},
                blob_bucket="overlays",
                blob_key="overlays/test.png",
                batch_id=batch_id,
            )

        assert prediction.review_eligible is False

    def test_cache_failure_does_not_raise(
        self, mock_session, queued_job, job_id, document_id, model_metadata_id, batch_id
    ):
        with (
            patch(
                "app.repositories.jobs.ClassificationJobRepository.get_by_id",
                return_value=queued_job,
            ),
            patch(
                "app.repositories.predictions.PredictionRepository.create",
                side_effect=lambda p: p,
            ),
            patch(
                "app.repositories.predictions.PredictionRepository.create_overlay",
                side_effect=lambda o: o,
            ),
            patch(
                "app.services.cache_invalidation.invalidate_after_classification",
                side_effect=Exception("Redis down"),
            ),
        ):
            svc = ClassificationJobService(mock_session)
            prediction = svc.persist_result(
                job_id=job_id,
                document_id=document_id,
                model_metadata_id=model_metadata_id,
                predicted_class="invoice",
                top1_confidence=0.55,
                class_scores={},
                blob_bucket="overlays",
                blob_key="overlays/test.png",
                batch_id=batch_id,
            )
        assert prediction is not None


class TestMarkRetryableFailure:
    def test_sets_retryable_failed_status(self, mock_session, queued_job, job_id):
        with patch(
            "app.repositories.jobs.ClassificationJobRepository.get_by_id",
            return_value=queued_job,
        ):
            svc = ClassificationJobService(mock_session)
            result = svc.mark_retryable_failure(job_id, "timeout")

        assert result.status == JobStatus.retryable_failed
        assert result.last_error == "timeout"
        mock_session.commit.assert_called_once()


class TestMarkTerminalFailure:
    def test_sets_terminal_failed_status(self, mock_session, queued_job, job_id):
        with patch(
            "app.repositories.jobs.ClassificationJobRepository.get_by_id",
            return_value=queued_job,
        ):
            svc = ClassificationJobService(mock_session)
            result = svc.mark_terminal_failure(job_id, "model corrupted")

        assert result.status == JobStatus.terminal_failed
        assert result.last_error == "model corrupted"
        mock_session.commit.assert_called_once()
