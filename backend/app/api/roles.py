from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/roles", tags=["roles"])


@router.put("/{user_id}")
async def update_user_role(user_id: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"Role update for user {user_id} is not implemented yet.",
    )
