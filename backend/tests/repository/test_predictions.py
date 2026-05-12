"""Unit tests for PredictionRepository."""

import uuid
from unittest.mock import MagicMock

import pytest

from app.db.models import OverlayAsset, Prediction
from app.repositories.predictions import PredictionRepository


class TestGetById:
    def test_returns_prediction_when_found(self, mock_session, sample_prediction):
        mock_session.execute.return_value.scalar_one_or_none.return_value = sample_prediction
        repo = PredictionRepository(mock_session)

        result = repo.get_by_id(sample_prediction.id)

        assert result is sample_prediction

    def test_returns_none_when_not_found(self, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        repo = PredictionRepository(mock_session)

        result = repo.get_by_id(uuid.uuid4())

        assert result is None


class TestGetByDocumentId:
    def test_returns_latest_prediction_for_document(
        self, mock_session, sample_prediction, document_id
    ):
        mock_session.execute.return_value.scalar_one_or_none.return_value = sample_prediction
        repo = PredictionRepository(mock_session)

        result = repo.get_by_document_id(document_id)

        assert result is sample_prediction

    def test_returns_none_when_no_prediction(self, mock_session, document_id):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        repo = PredictionRepository(mock_session)

        result = repo.get_by_document_id(document_id)

        assert result is None


class TestListReviewEligible:
    def test_returns_eligible_predictions(self, mock_session, sample_prediction):
        mock_session.execute.return_value.scalars.return_value.all.return_value = [sample_prediction]
        repo = PredictionRepository(mock_session)

        result = repo.list_review_eligible()

        assert result == [sample_prediction]

    def test_returns_empty_when_none_eligible(self, mock_session):
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        repo = PredictionRepository(mock_session)

        result = repo.list_review_eligible()

        assert result == []

    def test_accepts_limit_and_offset(self, mock_session):
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        repo = PredictionRepository(mock_session)

        result = repo.list_review_eligible(limit=10, offset=20)

        assert result == []


class TestCreate:
    def test_adds_prediction_to_session_and_flushes(self, mock_session):
        pred = MagicMock(spec=Prediction)
        repo = PredictionRepository(mock_session)

        result = repo.create(pred)

        mock_session.add.assert_called_once_with(pred)
        mock_session.flush.assert_called_once()
        assert result is pred


class TestUpdate:
    def test_flushes_session_and_returns_prediction(self, mock_session, sample_prediction):
        repo = PredictionRepository(mock_session)

        result = repo.update(sample_prediction)

        mock_session.flush.assert_called_once()
        assert result is sample_prediction


class TestCreateOverlay:
    def test_adds_overlay_to_session_and_flushes(self, mock_session):
        overlay = MagicMock(spec=OverlayAsset)
        repo = PredictionRepository(mock_session)

        result = repo.create_overlay(overlay)

        mock_session.add.assert_called_once_with(overlay)
        mock_session.flush.assert_called_once()
        assert result is overlay


class TestGetOverlayByPrediction:
    def test_returns_overlay_when_found(self, mock_session, prediction_id):
        overlay = MagicMock(spec=OverlayAsset)
        mock_session.execute.return_value.scalar_one_or_none.return_value = overlay
        repo = PredictionRepository(mock_session)

        result = repo.get_overlay_by_prediction(prediction_id)

        assert result is overlay

    def test_returns_none_when_no_overlay(self, mock_session, prediction_id):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        repo = PredictionRepository(mock_session)

        result = repo.get_overlay_by_prediction(prediction_id)

        assert result is None
