import uuid

from app.domain.errors import PermissionDenied
from app.domain.roles import Action, Resource
from app.infra.authz import casbin_enforcer


class AuthorizationService:
    """Business-facing permission checks backed by Casbin policies."""

    def can(
        self,
        user_id: uuid.UUID | str,
        resource: Resource | str,
        action: Action | str,
    ) -> bool:
        return casbin_enforcer.can(str(user_id), resource, action)

    def require_permission(
        self,
        user_id: uuid.UUID | str,
        resource: Resource | str,
        action: Action | str,
    ) -> None:
        if not self.can(user_id, resource, action):
            raise PermissionDenied(
                f"User {user_id} cannot {str(action)} {str(resource)}."
            )
