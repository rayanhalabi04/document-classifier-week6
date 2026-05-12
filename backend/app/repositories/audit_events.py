import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent


class AuditEventRepository:
    """SQL-only access for the audit_events table (append-only)."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, event: AuditEvent) -> AuditEvent:
        self.session.add(event)
        self.session.flush()
        return event

    def get_by_id(self, event_id: uuid.UUID) -> Optional[AuditEvent]:
        stmt = select(AuditEvent).where(AuditEvent.id == event_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def list(
        self,
        actor_user_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        stmt = (
            select(AuditEvent)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if actor_user_id is not None:
            stmt = stmt.where(AuditEvent.actor_user_id == actor_user_id)
        if action is not None:
            stmt = stmt.where(AuditEvent.action == action)
        if target_type is not None:
            stmt = stmt.where(AuditEvent.target_type == target_type)
        if target_id is not None:
            stmt = stmt.where(AuditEvent.target_id == target_id)
        return list(self.session.execute(stmt).scalars().all())
