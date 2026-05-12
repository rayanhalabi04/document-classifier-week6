import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.dependencies import get_authorization_service
from app.domain.errors import PermissionDenied
from app.main import app
from app.services.auth import current_active_user


class _AllowedAuthorizationService:
    def require_permission(
        self,
        user_id: object,
        resource: object,
        action: object,
    ) -> None:
        return None


class _DeniedAuthorizationService:
    def require_permission(
        self,
        user_id: object,
        resource: object,
        action: object,
    ) -> None:
        raise PermissionDenied("denied")


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), email="user@example.com")


def test_protected_route_rejects_missing_token() -> None:
    app.dependency_overrides.clear()
    client = TestClient(app)

    response = client.get("/batches")

    assert response.status_code == 401


def test_protected_route_returns_403_when_casbin_denies_user() -> None:
    app.dependency_overrides[current_active_user] = _user
    app.dependency_overrides[get_authorization_service] = _DeniedAuthorizationService
    client = TestClient(app)

    try:
        response = client.get("/batches")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_protected_route_accepts_user_when_casbin_allows_permission() -> None:
    app.dependency_overrides[current_active_user] = _user
    app.dependency_overrides[get_authorization_service] = _AllowedAuthorizationService
    client = TestClient(app)

    try:
        response = client.get("/batches")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 501
    assert response.json()["detail"] == "Batch listing is not implemented yet."
