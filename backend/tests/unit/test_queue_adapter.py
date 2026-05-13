"""Unit tests for app/infra/queue.py (T032)."""

import uuid
from unittest.mock import MagicMock, patch


class TestEnqueueClassificationJob:
    def test_returns_rq_job_id(self):
        from app.infra.queue import enqueue_classification_job

        mock_job = MagicMock()
        mock_job.id = "rq-job-abc-123"
        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = mock_job

        with (
            patch("app.infra.queue.get_redis_client"),
            patch("app.infra.queue.Queue", return_value=mock_queue),
        ):
            result = enqueue_classification_job(uuid.uuid4(), uuid.uuid4())

        assert result == "rq-job-abc-123"

    def test_enqueues_to_classification_queue(self):
        from app.infra.queue import enqueue_classification_job

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = MagicMock()

        with (
            patch("app.infra.queue.get_redis_client"),
            patch("app.infra.queue.Queue", return_value=mock_queue) as mock_cls,
        ):
            enqueue_classification_job(uuid.uuid4(), uuid.uuid4())

        assert mock_cls.call_args[0][0] == "classification"

    def test_passes_document_id_as_string(self):
        from app.infra.queue import enqueue_classification_job

        doc_id = uuid.uuid4()
        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = MagicMock()

        with (
            patch("app.infra.queue.get_redis_client"),
            patch("app.infra.queue.Queue", return_value=mock_queue),
        ):
            enqueue_classification_job(doc_id, uuid.uuid4())

        enqueue_args = mock_queue.enqueue.call_args[0]
        assert str(doc_id) in enqueue_args

    def test_uses_shared_redis_client(self):
        from app.infra.queue import enqueue_classification_job

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = MagicMock()

        with (
            patch("app.infra.queue.get_redis_client") as mock_redis,
            patch("app.infra.queue.Queue", return_value=mock_queue),
        ):
            enqueue_classification_job(uuid.uuid4(), uuid.uuid4())

        mock_redis.assert_called_once()


class TestCheckQueueHealth:
    def test_calls_ping(self):
        from app.infra.queue import check_queue_health

        mock_client = MagicMock()
        with patch("app.infra.queue.get_redis_client", return_value=mock_client):
            check_queue_health()
            mock_client.ping.assert_called_once()
