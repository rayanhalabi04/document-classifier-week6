"""Unit tests for PredictionReviewService."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.db.models import Prediction
from app.domain.errors import InvalidReviewLabel, PredictionNotFound, ReviewNotEligible
from app.services.prediction_review import PredictionReviewService


@pytest.fixture()
def mock_session():
    return MagicMock()


@pytest.fixture()
def reviewer_id():
    return uuid.uuid4()


@pytest.fixture()
def prediction_id():
    return uuid.uuid4()


@pytest.fixture()
def batch_id():
    return uuid.uuid4()


@pytest.fixture()
def eligible_prediction(prediction_id):
    pred = MagicMock(spec=Prediction)
    pred.id = prediction_id
    pred.predicted_class = "invoice"
    pred.top1_confidence = 0.55
    pred.review_eligible = True
    pred.review_label = None
    return pred


@pytest.fixture()
def ineligible_prediction(prediction_id):
    pred = MagicMock(spec=Prediction)
    pred.id = prediction_id
    pred.predicted_class = "invoice"
    pred.top1_confidence = 0.95
    pred.review_eligible = False
    return pred


def _make_authz_mock(can_relabel=True, is_admin=False):
    authz = MagicMock()
    authz.require_permission.return_value = None
    authz.can.return_value = is_admin
    return authz


class TestRelabelPredictionNotFound:
    def test_raises_prediction_not_found(
        self, mock_session, reviewer_id, prediction_id, batch_id
    ):
        with (
            patch(
                "app.repositories.predictions.PredictionRepository.get_by_id",
                return_value=None,
            ),
            patch(
                "app.services.prediction_review.AuthorizationService",
                return_value=_make_authz_mock(),
            ),
        ):
            svc = PredictionReviewService(mock_session)
            with pytest.raises(PredictionNotFound):
                svc.relabel(prediction_id, "invoice", reviewer_id, batch_id)


class TestRelabelNotEligible:
    def test_raises_review_not_eligible_for_high_confidence(
        self, mock_session, reviewer_id, batch_id, ineligible_prediction
    ):
        with (
            patch(
                "app.repositories.predictions.PredictionRepository.get_by_id",
                return_value=ineligible_prediction,
            ),
            patch(
                "app.services.prediction_review.AuthorizationService",
                return_value=_make_authz_mock(is_admin=False),
            ),
        ):
            svc = PredictionReviewService(mock_session)
            with pytest.raises(ReviewNotEligible):
                svc.relabel(ineligible_prediction.id, "letter", reviewer_id, batch_id)


class TestRelabelInvalidLabel:
    def test_raises_invalid_review_label(
        self, mock_session, reviewer_id, batch_id, eligible_prediction
    ):
        with (
            patch(
                "app.repositories.predictions.PredictionRepository.get_by_id",
                return_value=eligible_prediction,
            ),
            patch(
                "app.services.prediction_review.AuthorizationService",
                return_value=_make_authz_mock(),
            ),
        ):
            svc = PredictionReviewService(mock_session)
            with pytest.raises(InvalidReviewLabel):
                svc.relabel(
                    eligible_prediction.id, "NOT_A_CLASS", reviewer_id, batch_id
                )


class TestRelabelSuccess:
    def test_sets_review_label_and_reviewer(
        self, mock_session, reviewer_id, batch_id, eligible_prediction
    ):
        with (
            patch(
                "app.repositories.predictions.PredictionRepository.get_by_id",
                return_value=eligible_prediction,
            ),
            patch(
                "app.repositories.predictions.PredictionRepository.update",
                side_effect=lambda p: p,
            ),
            patch(
                "app.services.prediction_review.AuthorizationService",
                return_value=_make_authz_mock(),
            ),
            patch("app.services.cache_invalidation.invalidate_after_relabel"),
        ):
            svc = PredictionReviewService(mock_session)
            result = svc.relabel(
                eligible_prediction.id, "letter", reviewer_id, batch_id
            )

        assert eligible_prediction.review_label == "letter"
        assert eligible_prediction.reviewed_by_user_id == reviewer_id
        assert eligible_prediction.reviewed_at is not None
        mock_session.commit.assert_called_once()

    def test_normalizes_label_to_lowercase(
        self, mock_session, reviewer_id, batch_id, eligible_prediction
    ):
        with (
            patch(
                "app.repositories.predictions.PredictionRepository.get_by_id",
                return_value=eligible_prediction,
            ),
            patch(
                "app.repositories.predictions.PredictionRepository.update",
                side_effect=lambda p: p,
            ),
            patch(
                "app.services.prediction_review.AuthorizationService",
                return_value=_make_authz_mock(),
            ),
            patch("app.services.cache_invalidation.invalidate_after_relabel"),
        ):
            svc = PredictionReviewService(mock_session)
            svc.relabel(eligible_prediction.id, "  INVOICE  ", reviewer_id, batch_id)

        assert eligible_prediction.review_label == "invoice"

    def test_does_not_modify_original_predicted_class(
        self, mock_session, reviewer_id, batch_id, eligible_prediction
    ):
        original_class = eligible_prediction.predicted_class
        with (
            patch(
                "app.repositories.predictions.PredictionRepository.get_by_id",
                return_value=eligible_prediction,
            ),
            patch(
                "app.repositories.predictions.PredictionRepository.update",
                side_effect=lambda p: p,
            ),
            patch(
                "app.services.prediction_review.AuthorizationService",
                return_value=_make_authz_mock(),
            ),
            patch("app.services.cache_invalidation.invalidate_after_relabel"),
        ):
            svc = PredictionReviewService(mock_session)
            svc.relabel(eligible_prediction.id, "letter", reviewer_id, batch_id)

        assert eligible_prediction.predicted_class == original_class

    def test_cache_failure_does_not_raise(
        self, mock_session, reviewer_id, batch_id, eligible_prediction
    ):
        with (
            patch(
                "app.repositories.predictions.PredictionRepository.get_by_id",
                return_value=eligible_prediction,
            ),
            patch(
                "app.repositories.predictions.PredictionRepository.update",
                side_effect=lambda p: p,
            ),
            patch(
                "app.services.prediction_review.AuthorizationService",
                return_value=_make_authz_mock(),
            ),
            patch(
                "app.services.cache_invalidation.invalidate_after_relabel",
                side_effect=Exception("Redis down"),
            ),
        ):
            svc = PredictionReviewService(mock_session)
            result = svc.relabel(
                eligible_prediction.id, "letter", reviewer_id, batch_id
            )
        assert result is eligible_prediction


class TestAdminCanBypassConfidenceCheck:
    def test_admin_can_relabel_ineligible_prediction(
        self, mock_session, reviewer_id, batch_id, ineligible_prediction
    ):
        with (
            patch(
                "app.repositories.predictions.PredictionRepository.get_by_id",
                return_value=ineligible_prediction,
            ),
            patch(
                "app.repositories.predictions.PredictionRepository.update",
                side_effect=lambda p: p,
            ),
            patch(
                "app.services.prediction_review.AuthorizationService",
                return_value=_make_authz_mock(is_admin=True),
            ),
            patch("app.services.cache_invalidation.invalidate_after_relabel"),
        ):
            svc = PredictionReviewService(mock_session)
            result = svc.relabel(
                ineligible_prediction.id, "letter", reviewer_id, batch_id
            )
        assert result is ineligible_prediction
