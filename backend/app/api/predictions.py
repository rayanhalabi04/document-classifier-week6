import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import require_permission
from app.domain.errors import (
    InvalidReviewLabel,
    PermissionDenied,
    PredictionNotFound,
    ReviewNotEligible,
)
from app.domain.roles import Action, Resource
from app.infra.db import get_session
from app.services.prediction_review import PredictionReviewService

router = APIRouter(prefix="/predictions", tags=["predictions"])


class ReviewPredictionRequest(BaseModel):
    reviewed_label: str | None = None
    corrected_label: str | None = None

    @property
    def label(self) -> str | None:
        if self.reviewed_label is not None:
            return self.reviewed_label
        return self.corrected_label


class ReviewPredictionResponse(BaseModel):
    id: uuid.UUID
    predicted_class: str
    top1_confidence: float
    review_eligible: bool
    review_label: str
    reviewed_by_user_id: uuid.UUID
    reviewed_at: datetime | None


def get_prediction_review_service(
    session: Session = Depends(get_session),
) -> PredictionReviewService:
    """Build the prediction review service for API routes."""
    return PredictionReviewService(session)


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


@router.post(
    "/{prediction_id}/review",
    response_model=ReviewPredictionResponse,
)
async def review_prediction(
    prediction_id: uuid.UUID,
    request: ReviewPredictionRequest,
    reviewer=Depends(require_permission(Resource.PREDICTIONS, Action.RELABEL)),
    review_service: PredictionReviewService = Depends(get_prediction_review_service),
) -> Any:
    if request.reviewed_label is not None and request.corrected_label is not None:
        raise HTTPException(
            status_code=422,
            detail="Provide either reviewed_label or corrected_label, not both.",
        )
    if request.label is None:
        raise HTTPException(
            status_code=422,
            detail="reviewed_label or corrected_label is required.",
        )

    try:
        return review_service.relabel(
            prediction_id=prediction_id,
            review_label=request.label,
            reviewer_user_id=reviewer.id,
        )
    except PredictionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidReviewLabel as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except ReviewNotEligible as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except PermissionDenied as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
