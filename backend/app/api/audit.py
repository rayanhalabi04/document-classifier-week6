from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_audit_events() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Audit log endpoint is not implemented yet.",
    )
