"""Contract tests for T012 prediction review endpoint."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.api.dependencies import get_authorization_service
from app.api.predictions import get_prediction_review_service
from app.domain.errors import (
    InvalidReviewLabel,
    PermissionDenied,
    PredictionNotFound,
    ReviewNotEligible,
)
from app.main import app
from app.services.auth import current_active_user


PREDICTION_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
REVIEWER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


class _AllowedAuthorizationService:
    def require_permission(self, user_id, resource, action) -> None:
        return None


class _DeniedAuthorizationService:
    def require_permission(self, user_id, resource, action) -> None:
        raise PermissionDenied("denied")


def _reviewer() -> SimpleNamespace:
    return SimpleNamespace(id=REVIEWER_ID, email="reviewer@example.com")


def _reviewed_prediction(label: str = "memo") -> SimpleNamespace:
    return SimpleNamespace(
        id=PREDICTION_ID,
        predicted_class="letter",
        top1_confidence=0.42,
        review_eligible=True,
        review_label=label,
        reviewed_by_user_id=REVIEWER_ID,
        reviewed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_reviewer_can_review_eligible_low_confidence_prediction() -> None:
    service = Mock()
    service.relabel.return_value = _reviewed_prediction("memo")
    app.dependency_overrides[current_active_user] = _reviewer
    app.dependency_overrides[get_authorization_service] = _AllowedAuthorizationService
    app.dependency_overrides[get_prediction_review_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.post(
            f"/predictions/{PREDICTION_ID}/review",
            json={"reviewed_label": "memo"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["review_label"] == "memo"
    service.relabel.assert_called_once_with(
        prediction_id=PREDICTION_ID,
        review_label="memo",
        reviewer_user_id=REVIEWER_ID,
    )


def test_reviewer_cannot_relabel_high_confidence_prediction() -> None:
    service = Mock()
    service.relabel.side_effect = ReviewNotEligible("not eligible")
    app.dependency_overrides[current_active_user] = _reviewer
    app.dependency_overrides[get_authorization_service] = _AllowedAuthorizationService
    app.dependency_overrides[get_prediction_review_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.post(
            f"/predictions/{PREDICTION_ID}/review",
            json={"reviewed_label": "memo"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409


def test_auditor_cannot_relabel_prediction() -> None:
    app.dependency_overrides[current_active_user] = _reviewer
    app.dependency_overrides[get_authorization_service] = _DeniedAuthorizationService
    client = TestClient(app)

    try:
        response = client.post(
            f"/predictions/{PREDICTION_ID}/review",
            json={"reviewed_label": "memo"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_unauthenticated_review_request_is_rejected() -> None:
    app.dependency_overrides.clear()
    client = TestClient(app)

    response = client.post(
        f"/predictions/{PREDICTION_ID}/review",
        json={"reviewed_label": "memo"},
    )

    assert response.status_code == 401


def test_invalid_review_label_returns_validation_error() -> None:
    service = Mock()
    service.relabel.side_effect = InvalidReviewLabel("invalid label")
    app.dependency_overrides[current_active_user] = _reviewer
    app.dependency_overrides[get_authorization_service] = _AllowedAuthorizationService
    app.dependency_overrides[get_prediction_review_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.post(
            f"/predictions/{PREDICTION_ID}/review",
            json={"corrected_label": "not-a-class"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    service.relabel.assert_called_once_with(
        prediction_id=PREDICTION_ID,
        review_label="not-a-class",
        reviewer_user_id=REVIEWER_ID,
    )


def test_missing_prediction_returns_404() -> None:
    service = Mock()
    service.relabel.side_effect = PredictionNotFound("missing")
    app.dependency_overrides[current_active_user] = _reviewer
    app.dependency_overrides[get_authorization_service] = _AllowedAuthorizationService
    app.dependency_overrides[get_prediction_review_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.post(
            f"/predictions/{PREDICTION_ID}/review",
            json={"reviewed_label": "memo"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_prediction_review_route_appears_in_openapi() -> None:
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    path = response.json()["paths"]["/predictions/{prediction_id}/review"]
    assert "post" in path
