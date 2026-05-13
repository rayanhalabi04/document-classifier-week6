from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_live_returns_ok() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready_returns_ready_when_checks_pass(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.health.run_api_readiness_checks",
        lambda session_factory: [],
    )

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_health_ready_returns_503_when_checks_fail(monkeypatch) -> None:
    failures = ["postgres: Postgres connection failed."]
    monkeypatch.setattr(
        "app.api.health.run_api_readiness_checks",
        lambda session_factory: failures,
    )

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": failures,
        "message": "One or more readiness checks failed.",
    }


def test_health_routes_appear_in_openapi() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health/live" in response.json()["paths"]
    assert "/health/ready" in response.json()["paths"]
