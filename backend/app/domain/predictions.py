"""Prediction domain models."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class PredictionRead(BaseModel):
    """API response model for a single prediction detail."""

    id: uuid.UUID
    document_id: uuid.UUID
    source_filename: str | None = None
    predicted_class: str
    top1_confidence: float
    class_scores: dict | None = None
    review_eligible: bool
    review_label: str | None = None
    reviewed_by_user_id: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    overlay_blob_key: str | None = None
    created_at: datetime
