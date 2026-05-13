import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import OverlayAsset, Prediction


class PredictionRepository:
    """SQL-only access for the predictions and overlay_assets tables."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, prediction_id: uuid.UUID) -> Optional[Prediction]:
        stmt = select(Prediction).where(Prediction.id == prediction_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_document_id(self, document_id: uuid.UUID) -> Optional[Prediction]:
        """Return the latest prediction for a document."""
        stmt = (
            select(Prediction)
            .where(Prediction.document_id == document_id)
            .order_by(Prediction.created_at.desc())
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_review_eligible(
        self, limit: int = 50, offset: int = 0
    ) -> list[Prediction]:
        """Return predictions eligible for reviewer relabeling (confidence < 0.7)."""
        stmt = (
            select(Prediction)
            .where(Prediction.review_eligible.is_(True))
            .order_by(Prediction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.execute(stmt).scalars().all())

    def create(self, prediction: Prediction) -> Prediction:
        self.session.add(prediction)
        self.session.flush()
        return prediction

    def update(self, prediction: Prediction) -> Prediction:
        self.session.flush()
        return prediction

    def create_overlay(self, overlay: OverlayAsset) -> OverlayAsset:
        self.session.add(overlay)
        self.session.flush()
        return overlay

    def get_overlay_by_prediction(
        self, prediction_id: uuid.UUID
    ) -> Optional[OverlayAsset]:
        stmt = select(OverlayAsset).where(OverlayAsset.prediction_id == prediction_id)
        return self.session.execute(stmt).scalar_one_or_none()
