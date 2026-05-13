import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.api.audit import get_audit_log_service
from app.api.dependencies import get_authorization_service
from app.domain.audit import AuditEventRead
from app.domain.errors import PermissionDenied
from app.domain.roles import Action, Resource
from app.main import app
from app.services.auth import current_active_user


class _AuditAuthorizationService:
    def require_permission(self, user_id, resource, action) -> None:
        assert resource == Resource.AUDIT_LOGS
        assert action == Action.READ
        if user_id == _reviewer().id:
            raise PermissionDenied("denied")


def _admin() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        email="admin@example.com",
        roles=["admin"],
    )


def _auditor() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        email="auditor@example.com",
        roles=["auditor"],
    )


def _reviewer() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        email="reviewer@example.com",
        roles=["reviewer"],
    )


def _audit_event() -> AuditEventRead:
    return AuditEventRead(
        id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
        actor_id=_admin().id,
        action="role.assign",
        target="user:55555555-5555-5555-5555-555555555555",
        target_type="user",
        target_id="55555555-5555-5555-5555-555555555555",
        outcome="success",
        timestamp=datetime(2026, 1, 3, 12, 0, tzinfo=timezone.utc),
        metadata={"role": "auditor"},
        request_id="req-123",
    )


def test_unauthenticated_audit_events_request_is_rejected() -> None:
    app.dependency_overrides.clear()
    client = TestClient(app)

    response = client.get("/audit-events")

    assert response.status_code == 401


def test_admin_can_list_audit_events() -> None:
    service = Mock()
    service.list_events.return_value = [_audit_event()]
    app.dependency_overrides[current_active_user] = _admin
    app.dependency_overrides[get_authorization_service] = _AuditAuthorizationService
    app.dependency_overrides[get_audit_log_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.get("/audit-events")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "44444444-4444-4444-4444-444444444444",
            "actor_id": "11111111-1111-1111-1111-111111111111",
            "action": "role.assign",
            "target": "user:55555555-5555-5555-5555-555555555555",
            "target_type": "user",
            "target_id": "55555555-5555-5555-5555-555555555555",
            "outcome": "success",
            "timestamp": "2026-01-03T12:00:00Z",
            "metadata": {"role": "auditor"},
            "request_id": "req-123",
        }
    ]
    service.list_events.assert_called_once_with(
        actor_user_id=None,
        action=None,
        target_type=None,
        target_id=None,
        limit=50,
        offset=0,
    )


def test_auditor_can_list_audit_events() -> None:
    service = Mock()
    service.list_events.return_value = []
    app.dependency_overrides[current_active_user] = _auditor
    app.dependency_overrides[get_authorization_service] = _AuditAuthorizationService
    app.dependency_overrides[get_audit_log_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.get("/audit-events")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []


def test_reviewer_cannot_list_audit_events() -> None:
    app.dependency_overrides[current_active_user] = _reviewer
    app.dependency_overrides[get_authorization_service] = _AuditAuthorizationService
    client = TestClient(app)

    try:
        response = client.get("/audit-events")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_audit_events_route_appears_in_openapi() -> None:
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/audit-events" in response.json()["paths"]
