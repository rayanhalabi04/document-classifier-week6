"""Redis Queue adapter for enqueuing classification jobs.

Note: The full RQ adapter implementation is Member 4's domain (T032).
This module provides the minimal interface needed by the ingestion worker
to enqueue jobs. Member 4 may replace/enhance this with their full adapter.
"""

from __future__ import annotations

import os
import uuid

from redis import Redis
from rq import Queue


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
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    connection = Redis.from_url(redis_url)
    queue = Queue("classification", connection=connection)
    job = queue.enqueue(
        "app.workers.inference_worker.classify",
        str(document_id),
        str(model_metadata_id),
    )
    return job.id


def check_queue_health() -> None:
    """Verify the Redis Queue connection is available.

    Called by startup validation (both ingestion and inference workers).
    """
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    connection = Redis.from_url(redis_url)
    connection.ping()
