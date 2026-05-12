"""Contract tests for T008 JWT authentication."""

import uuid
from types import SimpleNamespace

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.api.users import get_role_management_service
from app.main import app
from app.services.auth import current_active_user

client = TestClient(app)


class _FakeRoleService:
    def __init__(self, roles: list[str]) -> None:
        self._roles = roles

    def get_active_roles(self, user_id: uuid.UUID) -> list[str]:
        return self._roles


def _active_user() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        email="reviewer@example.com",
        is_active=True,
    )


async def _inactive_user_rejected() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Inactive user",
    )


def test_auth_register_login_and_current_user_routes_exist() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]

    assert "/auth/register" in paths
    assert "/auth/jwt/login" in paths
    assert "/users/me" in paths


def test_current_user_rejects_missing_token() -> None:
    app.dependency_overrides.clear()

    response = client.get("/users/me")

    assert response.status_code == 401


def test_current_user_rejects_invalid_token(monkeypatch) -> None:
    app.dependency_overrides.clear()
    monkeypatch.setattr("app.services.auth.get_jwt_secret", lambda: "test-secret")

    response = client.get(
        "/users/me",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )

    assert response.status_code == 401


def test_current_user_returns_authenticated_user_fields() -> None:
    app.dependency_overrides[current_active_user] = _active_user
    app.dependency_overrides[get_role_management_service] = lambda: _FakeRoleService(
        roles=[]
    )

    try:
        response = client.get("/users/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "reviewer@example.com",
        "is_active": True,
        "roles": [],
    }


def test_current_user_includes_active_roles() -> None:
    app.dependency_overrides[current_active_user] = _active_user
    app.dependency_overrides[get_role_management_service] = lambda: _FakeRoleService(
        roles=["reviewer", "auditor"]
    )

    try:
        response = client.get("/users/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["roles"] == ["reviewer", "auditor"]


def test_current_user_rejects_inactive_user_from_auth_dependency() -> None:
    app.dependency_overrides[current_active_user] = _inactive_user_rejected

    try:
        response = client.get("/users/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


def test_jwt_secret_validation_reads_vault(monkeypatch) -> None:
    from app.services import startup_validation

    monkeypatch.setattr("app.services.auth.load_jwt_secret", lambda: "vault-secret")

    startup_validation.check_jwt_secret()


def test_jwt_secret_validation_rejects_placeholder(monkeypatch) -> None:
    import pytest

    from app.domain.errors import StartupValidationError
    from app.services import startup_validation

    monkeypatch.setattr(
        "app.services.auth.load_jwt_secret",
        lambda: "change-me-in-production",
    )

    with pytest.raises(StartupValidationError):
        startup_validation.check_jwt_secret()
