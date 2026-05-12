from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/batches", tags=["batches"])


@router.get("")
async def list_batches() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Batch listing is not implemented yet.",
    )


@router.get("/{batch_id}")
async def get_batch(batch_id: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"Batch detail for {batch_id} is not implemented yet.",
    )
