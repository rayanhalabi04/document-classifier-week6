from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/recent")
async def list_recent_predictions() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Recent predictions endpoint is not implemented yet.",
    )


@router.get("/{prediction_id}")
async def get_prediction(prediction_id: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"Prediction detail for {prediction_id} is not implemented yet.",
    )


@router.patch("/{prediction_id}/relabel")
async def relabel_prediction(prediction_id: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"Relabeling prediction {prediction_id} is not implemented yet.",
    )
