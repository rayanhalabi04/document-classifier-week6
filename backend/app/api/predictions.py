import uuid
from datetime import datetime
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_minio_adapter, require_permission
from app.domain.errors import (
    InvalidReviewLabel,
    PermissionDenied,
    PredictionNotFound,
    ReviewNotEligible,
)
from app.domain.predictions import PredictionRead
from app.domain.roles import Action, Resource
from app.db.models import OverlayAsset, Prediction
from app.infra.db import get_session
from app.infra.minio import MinIOAdapter
from app.repositories.predictions import PredictionRepository
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


@router.get("/recent", response_model=list[PredictionRead])
def list_recent_predictions(
    _user=Depends(require_permission(Resource.PREDICTIONS, Action.READ)),
    session: Session = Depends(get_session),
    review_eligible: bool | None = Query(None),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PredictionRead]:
    repo = PredictionRepository(session)
    if review_eligible is True:
        predictions = repo.list_review_eligible(limit=limit, offset=offset)
    else:
        predictions = repo.list_recent(limit=limit, offset=offset)

    return [
        _prediction_to_read(p, repo.get_overlay_by_prediction(p.id))
        for p in predictions
    ]


@router.get("/{prediction_id}", response_model=PredictionRead)
def get_prediction(
    prediction_id: uuid.UUID,
    _user=Depends(require_permission(Resource.PREDICTIONS, Action.READ)),
    session: Session = Depends(get_session),
) -> PredictionRead:
    repo = PredictionRepository(session)
    prediction = repo.get_by_id(prediction_id)
    if prediction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found.",
        )
    return _prediction_to_read(prediction, repo.get_overlay_by_prediction(prediction_id))


@router.get("/{prediction_id}/overlay")
def get_prediction_overlay(
    prediction_id: uuid.UUID,
    _user=Depends(require_permission(Resource.PREDICTIONS, Action.READ)),
    session: Session = Depends(get_session),
    minio: MinIOAdapter = Depends(get_minio_adapter),
) -> StreamingResponse:
    repo = PredictionRepository(session)
    overlay = repo.get_overlay_by_prediction(prediction_id)
    if overlay is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Overlay not found.",
        )

    data = minio.download_file(overlay.blob_bucket, overlay.blob_key)
    return StreamingResponse(BytesIO(data), media_type="image/png")


def _prediction_to_read(
    prediction: Prediction,
    overlay: OverlayAsset | None,
) -> PredictionRead:
    """Build a PredictionRead response from ORM objects."""
    source_filename = None
    if prediction.document is not None:
        source_filename = prediction.document.source_filename

    return PredictionRead(
        id=prediction.id,
        document_id=prediction.document_id,
        source_filename=source_filename,
        predicted_class=prediction.predicted_class,
        top1_confidence=prediction.top1_confidence,
        class_scores=prediction.class_scores_json,
        review_eligible=prediction.review_eligible,
        review_label=prediction.review_label,
        reviewed_by_user_id=prediction.reviewed_by_user_id,
        reviewed_at=prediction.reviewed_at,
        overlay_blob_key=overlay.blob_key if overlay else None,
        created_at=prediction.created_at,
    )


@router.patch("/{prediction_id}/relabel")
def relabel_prediction(
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
def review_prediction(
    prediction_id: uuid.UUID,
    request: ReviewPredictionRequest,
    reviewer=Depends(require_permission(Resource.PREDICTIONS, Action.RELABEL)),
    review_service: PredictionReviewService = Depends(get_prediction_review_service),
) -> ReviewPredictionResponse:
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
