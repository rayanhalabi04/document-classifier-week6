"""Contract tests for T010 admin user and role-management endpoints."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.api.dependencies import get_authorization_service
from app.api.users import get_role_management_service, get_user_management_service
from app.domain.errors import PermissionDenied
from app.domain.users import AdminUserProfile
from app.main import app
from app.services.auth import current_active_user


class _AllowedAuthorizationService:
    def require_permission(self, user_id, resource, action) -> None:
        return None


class _DeniedAuthorizationService:
    def require_permission(self, user_id, resource, action) -> None:
        raise PermissionDenied("denied")


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        email="admin@example.com",
    )


def _admin_profile(user_id: uuid.UUID | None = None) -> AdminUserProfile:
    return AdminUserProfile(
        id=user_id or uuid.UUID("22222222-2222-2222-2222-222222222222"),
        email="reviewer@example.com",
        is_active=True,
        is_verified=True,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        last_login_at=None,
        roles=["reviewer"],
    )


def test_admin_can_list_users() -> None:
    service = Mock()
    service.list_users.return_value = [_admin_profile()]
    app.dependency_overrides[current_active_user] = _user
    app.dependency_overrides[get_authorization_service] = _AllowedAuthorizationService
    app.dependency_overrides[get_user_management_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.get("/users")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["email"] == "reviewer@example.com"
    assert response.json()[0]["roles"] == ["reviewer"]
    assert "hashed_password" not in response.json()[0]
    service.list_users.assert_called_once_with(limit=50, offset=0)


def test_reviewer_or_auditor_cannot_list_users() -> None:
    app.dependency_overrides[current_active_user] = _user
    app.dependency_overrides[get_authorization_service] = _DeniedAuthorizationService
    client = TestClient(app)

    try:
        response = client.get("/users")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_unauthenticated_user_list_request_is_rejected() -> None:
    app.dependency_overrides.clear()
    client = TestClient(app)

    response = client.get("/users")

    assert response.status_code == 401


def test_admin_can_change_user_roles() -> None:
    target_user_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    service = Mock()
    service.replace_roles.return_value = [SimpleNamespace(role="auditor")]
    app.dependency_overrides[current_active_user] = _user
    app.dependency_overrides[get_authorization_service] = _AllowedAuthorizationService
    app.dependency_overrides[get_role_management_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.put(
            f"/users/{target_user_id}/roles",
            json={"roles": ["auditor"]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"user_id": str(target_user_id), "roles": ["auditor"]}
    service.replace_roles.assert_called_once_with(
        target_user_id=target_user_id,
        new_roles=["auditor"],
        acting_admin_id=_user().id,
    )


def test_non_admin_cannot_change_user_roles() -> None:
    target_user_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    app.dependency_overrides[current_active_user] = _user
    app.dependency_overrides[get_authorization_service] = _DeniedAuthorizationService
    client = TestClient(app)

    try:
        response = client.put(
            f"/users/{target_user_id}/roles",
            json={"roles": ["auditor"]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_admin_can_invite_user_without_claiming_delivery() -> None:
    service = Mock()
    service.invite_user.return_value = _admin_profile(
        uuid.UUID("44444444-4444-4444-4444-444444444444")
    )
    app.dependency_overrides[current_active_user] = _user
    app.dependency_overrides[get_authorization_service] = _AllowedAuthorizationService
    app.dependency_overrides[get_user_management_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.post(
            "/users/invitations",
            json={"email": "reviewer@example.com"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["email"] == "reviewer@example.com"
    service.invite_user.assert_called_once_with(
        email="reviewer@example.com",
        acting_admin_id=_user().id,
    )


def test_t010_paths_appear_in_openapi() -> None:
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/users/{user_id}/roles" in paths
    assert "/users/invitations" in paths
