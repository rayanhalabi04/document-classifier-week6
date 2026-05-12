"""Admin user-management service."""

import secrets
import uuid

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.db.models import User
from app.domain.users import AdminUserProfile
from app.repositories.roles import RoleRepository
from app.repositories.users import UserRepository
from app.services.audit_log import AuditLogService

_password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserInvitationAlreadyExists(ValueError):
    """Raised when an invitation targets an existing email address."""


class UserManagementService:
    """Handles admin user listing and invitation-aligned user creation."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._roles = RoleRepository(session)
        self._audit = AuditLogService(session)

    def list_users(self, limit: int = 100, offset: int = 0) -> list[AdminUserProfile]:
        """Return safe user fields with active role names."""
        users = self._users.list(limit=limit, offset=offset)
        return [self._to_admin_profile(user) for user in users]

    def invite_user(
        self,
        email: str,
        acting_admin_id: uuid.UUID,
        request_id: str | None = None,
    ) -> AdminUserProfile:
        """Create an inactive account that can later complete activation.

        There is no invitation token or mail delivery model in this codebase yet,
        so this method does not claim that an email was sent.
        """
        normalized_email = email.strip().lower()
        if self._users.get_by_email(normalized_email) is not None:
            raise UserInvitationAlreadyExists(
                f"User with email {normalized_email} already exists."
            )

        user = User(
            id=uuid.uuid4(),
            email=normalized_email,
            hashed_password=_password_context.hash(secrets.token_urlsafe(32)),
            is_active=False,
            is_superuser=False,
            is_verified=False,
        )
        self._users.create(user)
        self._audit.record(
            action="user.invited",
            outcome="success",
            actor_user_id=acting_admin_id,
            target_type="user",
            target_id=str(user.id),
            details={"email": normalized_email, "delivery": "not_configured"},
            request_id=request_id,
        )
        self._session.commit()
        return self._to_admin_profile(user)

    def _to_admin_profile(self, user: User) -> AdminUserProfile:
        roles = [role.role for role in self._roles.get_active_roles(user.id)]
        return AdminUserProfile(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at,
            roles=roles,
        )
