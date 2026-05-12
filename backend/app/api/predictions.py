from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import require_permission
from app.domain.roles import Action, Resource

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/recent")
async def list_recent_predictions(
    user=Depends(require_permission(Resource.PREDICTIONS, Action.READ)),
) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Recent predictions endpoint is not implemented yet.",
    )


@router.get("/{prediction_id}")
async def get_prediction(
    prediction_id: str,
    user=Depends(require_permission(Resource.PREDICTIONS, Action.READ)),
) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"Prediction detail for {prediction_id} is not implemented yet.",
    )


@router.patch("/{prediction_id}/relabel")
async def relabel_prediction(
    prediction_id: str,
    user=Depends(require_permission(Resource.PREDICTIONS, Action.RELABEL)),
) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"Relabeling prediction {prediction_id} is not implemented yet.",
    )
