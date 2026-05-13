"""Batch domain models."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class BatchRead(BaseModel):
    """API response model for a batch listing entry."""

    id: uuid.UUID
    source: str
    status: str
    document_count: int
    reviewable_count: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
