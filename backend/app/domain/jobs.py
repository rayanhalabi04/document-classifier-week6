"""Domain models for classification jobs dispatched to the inference worker.

Each ingested document gets one ClassificationJob tracked in Postgres
with RQ job lifecycle status (queued → running → succeeded / failed).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ClassificationJobRead(BaseModel):
    """Public view of a classification job record."""

    id: uuid.UUID
    document_id: uuid.UUID
    rq_job_id: str | None
    status: str
    attempt_count: int
    enqueued_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
