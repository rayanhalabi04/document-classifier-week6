from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import require_permission
from app.domain.roles import Action, Resource

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_audit_events(
    user=Depends(require_permission(Resource.AUDIT_LOGS, Action.READ)),
) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Audit log endpoint is not implemented yet.",
    )
