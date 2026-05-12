import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import require_permission
from app.api.users import get_role_management_service
from app.domain.errors import PermissionDenied
from app.domain.roles import Action, Resource
from app.services.role_management import RoleManagementService

router = APIRouter(prefix="/roles", tags=["roles"])


class ReplaceRolesRequest(BaseModel):
    roles: list[str]


@router.put("/{user_id}")
async def update_user_role(
    user_id: uuid.UUID,
    request: ReplaceRolesRequest,
    acting_user=Depends(require_permission(Resource.ROLES, Action.MANAGE)),
    role_service: RoleManagementService = Depends(get_role_management_service),
) -> dict[str, object]:
    try:
        assignments = role_service.replace_roles(
            target_user_id=user_id,
            new_roles=request.roles,
            acting_admin_id=acting_user.id,
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
