"""Audit log service — builds and persists append-only audit events.

All audit writes go through this service. Repositories never write audit rows
directly. The service does not commit; callers own the transaction.
"""

import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.models import AuditEvent
from app.domain.audit import AuditEventRead
from app.repositories.audit_events import AuditEventRepository


class AuditLogService:
    """Creates append-only audit events for operational and security actions."""

    def __init__(self, session: Session) -> None:
        self._repo = AuditEventRepository(session)

    def record(
        self,
        action: str,
        outcome: str,
        actor_user_id: Optional[uuid.UUID] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> AuditEvent:
        """Append one audit event. Flushes to session; caller commits.

        Args:
            action: Verb describing the operation (e.g. "prediction.relabel").
            outcome: "success" or "denied" or "failure".
            actor_user_id: UUID of the acting user, or None for system events.
            target_type: Entity kind (e.g. "prediction", "batch").
            target_id: String representation of the target entity ID.
            details: Arbitrary JSON-safe dict with safe contextual fields.
            request_id: API request ID or RQ job ID for traceability.
        """
        event = AuditEvent(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            outcome=outcome,
            details_json=details,
            request_id=request_id,
        )
        return self._repo.create(event)

    def list_events(
        self,
        actor_user_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEventRead]:
        """Return audit events in reverse chronological order."""
        events = self._repo.list(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            limit=limit,
            offset=offset,
        )
        return [self._to_read_model(event) for event in events]

    @staticmethod
    def _to_read_model(event: AuditEvent) -> AuditEventRead:
        target = None
        if event.target_type and event.target_id:
            target = f"{event.target_type}:{event.target_id}"
        elif event.target_type:
            target = event.target_type
        elif event.target_id:
            target = event.target_id

        return AuditEventRead(
            id=event.id,
            actor_id=event.actor_user_id,
            action=event.action,
            target=target,
            target_type=event.target_type,
            target_id=event.target_id,
            outcome=event.outcome,
            timestamp=event.created_at,
            metadata=event.details_json,
            request_id=event.request_id,
        )
