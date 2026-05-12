"""Contract tests for T008 JWT authentication."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_auth_register_login_and_current_user_routes_exist() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]

    assert "/auth/register" in paths
    assert "/auth/jwt/login" in paths
    assert "/users/me" in paths


def test_current_user_rejects_missing_token() -> None:
    response = client.get("/users/me")

    assert response.status_code == 401


def test_current_user_rejects_invalid_token(monkeypatch) -> None:
    monkeypatch.setattr("app.services.auth.get_jwt_secret", lambda: "test-secret")

    response = client.get(
        "/users/me",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )

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
