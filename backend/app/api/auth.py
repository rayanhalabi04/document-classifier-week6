from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register_user() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="User registration is not implemented yet.",
    )


@router.post("/login")
async def login_user() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="JWT login is not implemented yet.",
    )


@router.get("/me")
async def get_current_user() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Current user endpoint is not implemented yet.",
    )