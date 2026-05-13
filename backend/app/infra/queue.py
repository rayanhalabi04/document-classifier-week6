"""Redis Queue adapter for enqueuing classification jobs."""

from __future__ import annotations

import uuid

from rq import Queue, Retry

from app.infra.redis import get_redis_client

# Retry up to 3 times with exponential backoff (10s, 30s, 60s).
# The job is marked retryable_failed in the DB each time it fails; once retries
# are exhausted, the job moves to RQ's failed-job registry and stays in
# retryable_failed state until manual intervention.
_CLASSIFICATION_RETRY = Retry(max=3, interval=[10, 30, 60])


def enqueue_classification_job(
    document_id: uuid.UUID,
    model_metadata_id: uuid.UUID,
) -> str:
    """Enqueue a classification job via Redis Queue.

    Args:
        document_id: UUID of the document to classify.
        model_metadata_id: UUID of the model metadata record.

    Returns:
        The RQ job ID as a string.
    """
    connection = get_redis_client()
    queue = Queue("classification", connection=connection)
    job = queue.enqueue(
        "app.workers.inference_worker.classify_document",
        str(document_id),
        str(model_metadata_id),
        retry=_CLASSIFICATION_RETRY,
    )
    return job.id


def check_queue_health() -> None:
    """Verify the Redis Queue connection is available.

    Called by startup validation for both ingestion and inference workers.
    Raises redis.exceptions.ConnectionError on failure.
    """
    get_redis_client().ping()
