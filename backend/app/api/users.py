from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import require_permission
from app.domain.roles import Action, Resource
from app.services.auth import UserRead, current_active_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_current_user(
    user=Depends(current_active_user),
):
    return user


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
