"""Shared API dependencies for authentication and authorization."""

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, status

from app.domain.errors import PermissionDenied
from app.domain.roles import Action, Resource
from app.services.auth import current_active_user
from app.services.authorization import AuthorizationService


def get_authorization_service() -> AuthorizationService:
    """Return the Casbin-backed authorization service."""
    return AuthorizationService()


def require_permission(
    resource: Resource | str,
    action: Action | str,
) -> Callable[..., Any]:
    """Require an authenticated user with the requested Casbin permission."""

    async def dependency(
        user: Any = Depends(current_active_user),
        authorization: AuthorizationService = Depends(get_authorization_service),
    ) -> Any:
        try:
            authorization.require_permission(user.id, resource, action)
        except PermissionDenied as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized for this operation.",
            ) from exc
        return user

    return dependency
