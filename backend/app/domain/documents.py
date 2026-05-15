"""Domain models for scanned documents flowing through the ingestion pipeline.

Documents enter via SFTP, are validated as TIFFs, uploaded to MinIO,
and enqueued for classification.  This module defines the read model
exposed by the API layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentRead(BaseModel):
    """Public view of an ingested document record."""

    id: uuid.UUID
    batch_id: uuid.UUID
    source_path: str
    source_filename: str
    source_size_bytes: int | None
    source_checksum: str | None
    mime_type: str | None
    ingestion_status: str
    failure_reason: str | None
    blob_bucket: str | None
    blob_key: str | None
    created_at: datetime
    updated_at: datetime
