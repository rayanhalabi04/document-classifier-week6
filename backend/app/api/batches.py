from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import require_permission
from app.domain.roles import Action, Resource

router = APIRouter(prefix="/batches", tags=["batches"])


@router.get("")
async def list_batches(
    user=Depends(require_permission(Resource.BATCHES, Action.READ)),
) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Batch listing is not implemented yet.",
    )


@router.get("/{batch_id}")
async def get_batch(
    batch_id: str,
    user=Depends(require_permission(Resource.BATCHES, Action.READ)),
) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"Batch detail for {batch_id} is not implemented yet.",
    )
