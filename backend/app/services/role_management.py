"""Role management service — admin-only role assignment and revocation.

Rules:
- Only admins can assign or revoke roles.
- Assigning a role that is already active is a no-op (idempotent).
- Replacing roles revokes all current active roles then assigns the new set.
- Every change is audited.
- Cache is invalidated after a successful commit.
"""

from app.infra.logging import get_logger
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import RoleAssignment
from app.domain.errors import PermissionDenied
from app.infra.authz import casbin_enforcer
from app.repositories.roles import RoleRepository
from app.repositories.users import UserRepository
from app.services.audit_log import AuditLogService
from app.services.authorization import AuthorizationService
from app.services.cache_invalidation import invalidate_user_roles

logger = get_logger(__name__)

VALID_ROLES = {"admin", "reviewer", "auditor"}


class RoleManagementService:
    """Handles admin role assignment, revocation, and replacement."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._roles = RoleRepository(session)
        self._users = UserRepository(session)
        self._audit = AuditLogService(session)
        self._authz = AuthorizationService()

    def assign_role(
        self,
        target_user_id: uuid.UUID,
        role: str,
        acting_admin_id: uuid.UUID,
        request_id: str | None = None,
    ) -> RoleAssignment | None:
        """Assign a role to a user. No-op if the role is already active.

        Args:
            target_user_id: User receiving the role.
            role: One of admin, reviewer, auditor.
            acting_admin_id: Admin performing the action (for audit).
            request_id: API request ID for traceability.

        Returns:
            The new RoleAssignment, or None if already active.

        Raises:
            PermissionDenied: If acting user is not an admin.
            ValueError: If role is not a valid role name.
        """
        self._require_admin(acting_admin_id)
        self._validate_role(role)

        if self._roles.has_active_role(target_user_id, role):
            logger.info(
                "assign_role no-op: user %s already has role '%s'",
                target_user_id,
                role,
            )
            return None

        assignment = RoleAssignment(
            id=uuid.uuid4(),
            user_id=target_user_id,
            role=role,
            assigned_by_user_id=acting_admin_id,
            assigned_at=datetime.now(timezone.utc),
        )
        self._roles.create(assignment)

        self._audit.record(
            action="role.assigned",
            outcome="success",
            actor_user_id=acting_admin_id,
            target_type="user",
            target_id=str(target_user_id),
            details={"role": role},
            request_id=request_id,
        )

        self._session.commit()

        # Sync Casbin AFTER commit so a rollback doesn't desync it
        casbin_enforcer.assign_role(str(target_user_id), role)

        try:
            invalidate_user_roles(target_user_id)
        except Exception:
            logger.warning(
                "Cache invalidation failed after role assignment for user %s",
                target_user_id,
            )

        return assignment

    def revoke_role(
        self,
        target_user_id: uuid.UUID,
        role: str,
        acting_admin_id: uuid.UUID,
        request_id: str | None = None,
    ) -> None:
        """Revoke a specific active role from a user.

        Raises:
            PermissionDenied: If acting user is not an admin.
            ValueError: If the role is not currently active.
        """
        self._require_admin(acting_admin_id)
        self._validate_role(role)

        active = self._roles.get_active_roles(target_user_id)
        target = next((r for r in active if r.role == role), None)

        if target is None:
            raise ValueError(
                f"User {target_user_id} does not have active role '{role}'."
            )

        self._roles.revoke(target.id)

        self._audit.record(
            action="role.revoked",
            outcome="success",
            actor_user_id=acting_admin_id,
            target_type="user",
            target_id=str(target_user_id),
            details={"role": role},
            request_id=request_id,
        )

        self._session.commit()

        # Sync Casbin AFTER commit so a rollback doesn't desync it
        casbin_enforcer.remove_role(str(target_user_id), role)

        try:
            invalidate_user_roles(target_user_id)
        except Exception:
            logger.warning(
                "Cache invalidation failed after role revocation for user %s",
                target_user_id,
            )

    def replace_roles(
        self,
        target_user_id: uuid.UUID,
        new_roles: list[str],
        acting_admin_id: uuid.UUID,
        request_id: str | None = None,
    ) -> list[RoleAssignment]:
        """Replace all active roles for a user with a new set.

        Revokes every current active role then assigns each role in new_roles.
        Runs in a single transaction.

        Args:
            target_user_id: User whose roles are being replaced.
            new_roles: Complete list of roles to assign (can be empty to strip all).
            acting_admin_id: Admin performing the action.
            request_id: API request ID for traceability.

        Returns:
            List of newly created RoleAssignment records.

        Raises:
            PermissionDenied: If acting user is not an admin.
            ValueError: If any role name is invalid.
        """
        self._require_admin(acting_admin_id)
        for role in new_roles:
            self._validate_role(role)

        self._roles.revoke_all_for_user(target_user_id)

        assignments = []
        for role in new_roles:
            assignment = RoleAssignment(
                id=uuid.uuid4(),
                user_id=target_user_id,
                role=role,
                assigned_by_user_id=acting_admin_id,
                assigned_at=datetime.now(timezone.utc),
            )
            self._roles.create(assignment)
            assignments.append(assignment)

        self._audit.record(
            action="role.replaced",
            outcome="success",
            actor_user_id=acting_admin_id,
            target_type="user",
            target_id=str(target_user_id),
            details={"new_roles": new_roles},
            request_id=request_id,
        )

        self._session.commit()

        # Sync Casbin AFTER commit so a rollback doesn't desync it
        casbin_enforcer.remove_roles_for_user(str(target_user_id))
        for role in new_roles:
            casbin_enforcer.assign_role(str(target_user_id), role)

        try:
            invalidate_user_roles(target_user_id)
        except Exception:
            logger.warning(
                "Cache invalidation failed after role replacement for user %s",
                target_user_id,
            )

        return assignments

    def get_active_roles(self, user_id: uuid.UUID) -> list[str]:
        """Return the list of active role names for a user."""
        return [r.role for r in self._roles.get_active_roles(user_id)]

    # ------------------------------------------------------------------

    def _require_admin(self, user_id: uuid.UUID) -> None:
        self._authz.require_permission(user_id, "roles", "manage")

    def _validate_role(self, role: str) -> None:
        if role not in VALID_ROLES:
            raise ValueError(
                f"'{role}' is not a valid role. Must be one of: {sorted(VALID_ROLES)}."
            )
