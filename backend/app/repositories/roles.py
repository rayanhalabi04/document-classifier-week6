import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RoleAssignment


class RoleRepository:
    """SQL-only access for the role_assignments table."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_active_roles(self, user_id: uuid.UUID) -> list[RoleAssignment]:
        """Return all currently active (non-revoked) roles for a user."""
        stmt = select(RoleAssignment).where(
            RoleAssignment.user_id == user_id,
            RoleAssignment.revoked_at.is_(None),
        )
        return list(self.session.execute(stmt).scalars().all())

    def has_active_role(self, user_id: uuid.UUID, role: str) -> bool:
        stmt = select(RoleAssignment).where(
            RoleAssignment.user_id == user_id,
            RoleAssignment.role == role,
            RoleAssignment.revoked_at.is_(None),
        )
        return self.session.execute(stmt).scalar_one_or_none() is not None

    def get_by_id(self, role_id: uuid.UUID) -> Optional[RoleAssignment]:
        stmt = select(RoleAssignment).where(RoleAssignment.id == role_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def create(self, role_assignment: RoleAssignment) -> RoleAssignment:
        self.session.add(role_assignment)
        self.session.flush()
        return role_assignment

    def revoke(
        self,
        role_id: uuid.UUID,
        revoked_at: Optional[datetime] = None,
    ) -> Optional[RoleAssignment]:
        """Set revoked_at on a role assignment to deactivate it."""
        role = self.get_by_id(role_id)
        if role is None:
            return None
        role.revoked_at = revoked_at or datetime.now(timezone.utc)
        self.session.flush()
        return role

    def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        """Revoke all active roles for a user (used during role replacement)."""
        active = self.get_active_roles(user_id)
        now = datetime.now(timezone.utc)
        for role in active:
            role.revoked_at = now
        self.session.flush()
