import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import require_permission
from app.domain.errors import PermissionDenied
from app.domain.roles import Action, Resource
from app.domain.users import AdminUserProfile, CurrentUserProfile
from app.infra.db import get_session
from app.services.auth import current_active_user
from app.services.role_management import RoleManagementService
from app.services.user_management import (
    UserInvitationAlreadyExists,
    UserManagementService,
)

router = APIRouter(prefix="/users", tags=["users"])


class InviteUserRequest(BaseModel):
    email: str


class ReplaceRolesRequest(BaseModel):
    roles: list[str]


def get_role_management_service(
    session: Session = Depends(get_session),
) -> RoleManagementService:
    """Build the role service used by user-facing API dependencies."""
    return RoleManagementService(session)


def get_user_management_service(
    session: Session = Depends(get_session),
) -> UserManagementService:
    """Build the admin user-management service."""
    return UserManagementService(session)


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


@router.get("", response_model=list[AdminUserProfile])
async def list_users(
    _admin=Depends(require_permission(Resource.USERS, Action.MANAGE)),
    user_service: UserManagementService = Depends(get_user_management_service),
) -> list[AdminUserProfile]:
    return user_service.list_users()


@router.post(
    "/invitations",
    response_model=AdminUserProfile,
    status_code=status.HTTP_201_CREATED,
)
async def invite_user(
    request: InviteUserRequest,
    acting_admin=Depends(require_permission(Resource.USERS, Action.MANAGE)),
    user_service: UserManagementService = Depends(get_user_management_service),
) -> AdminUserProfile:
    try:
        return user_service.invite_user(
            email=request.email,
            acting_admin_id=acting_admin.id,
        )
    except UserInvitationAlreadyExists as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.put("/{user_id}/roles")
async def replace_user_roles(
    user_id: uuid.UUID,
    request: ReplaceRolesRequest,
    acting_admin=Depends(require_permission(Resource.ROLES, Action.MANAGE)),
    role_service: RoleManagementService = Depends(get_role_management_service),
) -> dict[str, object]:
    try:
        assignments = role_service.replace_roles(
            target_user_id=user_id,
            new_roles=request.roles,
            acting_admin_id=acting_admin.id,
        )
    except PermissionDenied as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {"user_id": str(user_id), "roles": [role.role for role in assignments]}
