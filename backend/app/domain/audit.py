import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEventRead(BaseModel):
    """Stable API representation of an audit event."""

    id: uuid.UUID
    actor_id: uuid.UUID | None = None
    action: str
    target: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    outcome: str
    timestamp: datetime
    metadata: dict[str, Any] | None = None
    request_id: str | None = None
