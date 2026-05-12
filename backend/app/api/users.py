from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_permission
from app.domain.roles import Action, Resource
from app.domain.users import CurrentUserProfile
from app.infra.db import get_session
from app.services.auth import current_active_user
from app.services.role_management import RoleManagementService

router = APIRouter(prefix="/users", tags=["users"])


def get_role_management_service(
    session: Session = Depends(get_session),
) -> RoleManagementService:
    """Build the role service used by user-facing API dependencies."""
    return RoleManagementService(session)


@router.get("/me", response_model=CurrentUserProfile)
async def get_current_user(
    user=Depends(current_active_user),
    role_service: RoleManagementService = Depends(get_role_management_service),
) -> CurrentUserProfile:
    # TODO: Cache this profile when app.infra.cache exposes a usable read/write API.
    roles = role_service.get_active_roles(user.id)
    return CurrentUserProfile(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        roles=roles,
    )


@router.get("")
async def list_users() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="User listing is not implemented yet.",
    )


@router.post("/invite")
async def invite_user(
    user=Depends(require_permission(Resource.USERS, Action.MANAGE)),
) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="User invitation is not implemented yet.",
    )
