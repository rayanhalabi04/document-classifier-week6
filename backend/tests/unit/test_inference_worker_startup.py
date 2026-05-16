"""Unit tests for inference worker (T028, T029, T030, T037)."""

import uuid
from unittest.mock import MagicMock, patch

import pytest


class TestInferenceWorkerStartup:
    """T028 — startup validation gates the RQ worker."""

    def test_exits_when_startup_checks_fail(self):
        from app.workers import inference_worker

        with patch(
            "app.workers.inference_worker.run_inference_worker_checks",
            return_value=["classifier_assets: missing", "redis: down"],
        ):
            with pytest.raises(SystemExit) as exc_info:
                inference_worker.main()

        assert exc_info.value.code == 1

    def test_starts_worker_when_checks_pass(self):
        from app.workers import inference_worker

        with (
            patch(
                "app.workers.inference_worker.run_inference_worker_checks",
                return_value=[],
            ),
            patch("app.config.apply_vault_secrets"),
            patch("app.infra.redis.get_redis_client"),
            patch("rq.Worker") as mock_worker_cls,
            patch("rq.Queue") as mock_queue_cls,
        ):
            mock_worker_cls.return_value.work.return_value = None
            inference_worker.main()

        mock_queue_cls.assert_called_once()
        assert mock_queue_cls.call_args[0][0] == "classification"
        mock_worker_cls.return_value.work.assert_called_once()


class TestValidateClassifierAssets:
    """T028 — convenience wrapper for default-path validation."""

    def test_calls_validate_all_with_default_paths(self):
        from app.classifier import validation

        with patch("app.classifier.validation.validate_all") as mock_validate:
            validation.validate_classifier_assets()

        assert mock_validate.call_count == 1
        kwargs = mock_validate.call_args.kwargs
        assert kwargs["classifier_path"].name == "classifier.pt"
        assert kwargs["model_card_path"].name == "model_card.json"


class TestClassifyDocument:
    """T029/T030/T037 — RQ job runs inference, uploads overlay, persists result."""

    def _setup_session_mocks(self, doc_present=True, active_job_present=True):
        """Build all the patched dependencies the job function calls."""
        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()

        mock_doc = MagicMock()
        mock_doc.blob_key = "originals/abc.tiff"
        mock_doc.batch_id = uuid.uuid4()

        mock_session = MagicMock()
        mock_session_ctx = MagicMock()
        mock_session_ctx.__enter__.return_value = mock_session
        mock_session_ctx.__exit__.return_value = False

        mock_job_repo = MagicMock()
        mock_job_repo.get_active_by_document.return_value = (
            mock_job if active_job_present else None
        )

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_id.return_value = mock_doc if doc_present else None

        mock_svc = MagicMock()

        return {
            "session_ctx": mock_session_ctx,
            "job": mock_job,
            "doc": mock_doc,
            "job_repo": mock_job_repo,
            "doc_repo": mock_doc_repo,
            "svc": mock_svc,
        }

    def test_raises_when_no_active_job_found(self):
        from app.domain.errors import ClassificationError
        from app.workers import inference_worker

        m = self._setup_session_mocks(active_job_present=False)

        with (
            patch(
                "app.workers.inference_worker.SessionFactory",
                return_value=m["session_ctx"],
            ),
            patch(
                "app.workers.inference_worker.ClassificationJobRepository",
                return_value=m["job_repo"],
            ),
            patch(
                "app.workers.inference_worker.DocumentRepository",
                return_value=m["doc_repo"],
            ),
            patch(
                "app.workers.inference_worker.ClassificationJobService",
                return_value=m["svc"],
            ),
        ):
            with pytest.raises(ClassificationError):
                inference_worker.classify_document(str(uuid.uuid4()), str(uuid.uuid4()))

    def test_marks_running_then_persists_on_success(self):
        from app.workers import inference_worker

        m = self._setup_session_mocks()

        mock_result = MagicMock()
        mock_result.predicted_class = "letter"
        mock_result.top1_confidence = 0.92
        mock_result.class_scores = {"letter": 0.92}

        with (
            patch(
                "app.workers.inference_worker.SessionFactory",
                return_value=m["session_ctx"],
            ),
            patch(
                "app.workers.inference_worker.ClassificationJobRepository",
                return_value=m["job_repo"],
            ),
            patch(
                "app.workers.inference_worker.DocumentRepository",
                return_value=m["doc_repo"],
            ),
            patch(
                "app.workers.inference_worker.ClassificationJobService",
                return_value=m["svc"],
            ),
            patch(
                "app.workers.inference_worker._run_pipeline",
                return_value=(mock_result, b"PNG_BYTES"),
            ),
            patch("app.workers.inference_worker.MinIOAdapter") as mock_minio_cls,
        ):
            mock_minio = MagicMock()
            mock_minio_cls.return_value = mock_minio

            inference_worker.classify_document(str(uuid.uuid4()), str(uuid.uuid4()))

        m["svc"].mark_running.assert_called_once_with(m["job"].id)
        mock_minio.upload_file.assert_called_once()
        upload_kwargs = mock_minio.upload_file.call_args.kwargs
        assert upload_kwargs["bucket"] == "overlays"
        assert upload_kwargs["data"] == b"PNG_BYTES"
        assert upload_kwargs["content_type"] == "image/png"

        m["svc"].persist_result.assert_called_once()
        m["svc"].mark_retryable_failure.assert_not_called()

    def test_marks_retryable_failure_and_reraises_on_error(self):
        from app.workers import inference_worker

        m = self._setup_session_mocks()

        with (
            patch(
                "app.workers.inference_worker.SessionFactory",
                return_value=m["session_ctx"],
            ),
            patch(
                "app.workers.inference_worker.ClassificationJobRepository",
                return_value=m["job_repo"],
            ),
            patch(
                "app.workers.inference_worker.DocumentRepository",
                return_value=m["doc_repo"],
            ),
            patch(
                "app.workers.inference_worker.ClassificationJobService",
                return_value=m["svc"],
            ),
            patch(
                "app.workers.inference_worker._run_pipeline",
                side_effect=RuntimeError("model exploded"),
            ),
        ):
            with pytest.raises(RuntimeError, match="model exploded"):
                inference_worker.classify_document(str(uuid.uuid4()), str(uuid.uuid4()))

        m["svc"].mark_retryable_failure.assert_called_once()
        m["svc"].persist_result.assert_not_called()
