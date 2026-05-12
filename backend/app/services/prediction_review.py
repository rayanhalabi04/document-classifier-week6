"""Prediction review service — handles reviewer relabeling of predictions.

Rules:
- Only predictions with top1_confidence < 0.7 are eligible for relabeling.
- The original predicted_class and top1_confidence are never modified.
- review_label holds the reviewer's override.
- Every relabel is audited.
- Cache is invalidated after a successful commit.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Prediction
from app.domain.errors import InvalidReviewLabel, PredictionNotFound, ReviewNotEligible
from app.domain.roles import Action, Resource
from app.repositories.predictions import PredictionRepository
from app.services.audit_log import AuditLogService
from app.services.authorization import AuthorizationService
from app.services.cache_invalidation import invalidate_after_relabel

logger = logging.getLogger(__name__)

# The 16 RVL-CDIP layout classes — must match model_card.json
RVL_CDIP_CLASSES = {
    "letter",
    "form",
    "email",
    "handwritten",
    "advertisement",
    "scientific report",
    "scientific publication",
    "specification",
    "file folder",
    "news article",
    "budget",
    "invoice",
    "presentation",
    "questionnaire",
    "resume",
    "memo",
}

REVIEW_CONFIDENCE_THRESHOLD = 0.7


class PredictionReviewService:
    """Handles reviewer relabeling of low-confidence predictions."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._predictions = PredictionRepository(session)
        self._audit = AuditLogService(session)
        self._authz = AuthorizationService()

    def relabel(
        self,
        prediction_id: uuid.UUID,
        review_label: str,
        reviewer_user_id: uuid.UUID,
        batch_id: uuid.UUID | None = None,
        request_id: str | None = None,
    ) -> Prediction:
        """Apply a reviewer label to an eligible prediction.

        Args:
            prediction_id: The prediction to relabel.
            review_label: The reviewer's chosen RVL-CDIP class.
            reviewer_user_id: User performing the relabel (for audit + record).
            batch_id: Parent batch (used for cache invalidation). If omitted,
                it is derived from the prediction's document.
            request_id: API request ID for audit traceability.

        Returns:
            The updated Prediction record.

        Raises:
            PredictionNotFound: If no prediction exists with that ID.
            ReviewNotEligible: If top1_confidence >= 0.7.
            InvalidReviewLabel: If the label is not a valid RVL-CDIP class.
        """
        prediction = self._predictions.get_by_id(prediction_id)
        if prediction is None:
            raise PredictionNotFound(f"Prediction {prediction_id} not found.")

        self._authz.require_permission(
            reviewer_user_id,
            Resource.PREDICTIONS,
            Action.RELABEL,
        )

        can_bypass_confidence = self._authz.can(
            reviewer_user_id,
            Resource.ROLES,
            Action.MANAGE,
        )
        if not can_bypass_confidence and not prediction.review_eligible:
            raise ReviewNotEligible(
                f"Prediction {prediction_id} is not eligible for review "
                f"(confidence {prediction.top1_confidence:.3f} >= {REVIEW_CONFIDENCE_THRESHOLD})."
            )

        normalized = review_label.strip().lower()
        if normalized not in RVL_CDIP_CLASSES:
            raise InvalidReviewLabel(
                f"'{review_label}' is not a valid RVL-CDIP class."
            )

        prediction.review_label = normalized
        prediction.reviewed_by_user_id = reviewer_user_id
        prediction.reviewed_at = datetime.now(timezone.utc)
        self._predictions.update(prediction)

        self._audit.record(
            action="prediction.relabeled",
            outcome="success",
            actor_user_id=reviewer_user_id,
            target_type="prediction",
            target_id=str(prediction_id),
            details={
                "original_class": prediction.predicted_class,
                "review_label": normalized,
                "top1_confidence": prediction.top1_confidence,
            },
            request_id=request_id,
        )

        cache_batch_id = batch_id
        if cache_batch_id is None:
            cache_batch_id = prediction.document.batch_id

        self._session.commit()

        try:
            invalidate_after_relabel(cache_batch_id, prediction_id)
        except Exception:
            logger.warning(
                "Cache invalidation failed after relabel of prediction %s", prediction_id
            )

        return prediction
