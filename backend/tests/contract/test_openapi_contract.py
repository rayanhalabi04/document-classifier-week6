from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_openapi_schema_is_available() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200

    schema = response.json()
    assert schema["info"]["title"] == "Document Classifier API"


def test_expected_route_prefixes_exist() -> None:
    response = client.get("/openapi.json")
    schema = response.json()

    paths = schema["paths"].keys()

    expected_prefixes = [
        "/auth",
        "/users",
        "/roles",
        "/batches",
        "/predictions",
        "/audit",
        "/health",
    ]

    for prefix in expected_prefixes:
        assert any(path.startswith(prefix) for path in paths), f"Missing route prefix: {prefix}"


def test_health_endpoints_exist_and_work() -> None:
    live_response = client.get("/health/live")
    ready_response = client.get("/health/ready")

    assert live_response.status_code == 200
    assert live_response.json() == {"status": "ok"}

    assert ready_response.status_code == 200
    assert ready_response.json()["status"] == "not_ready"


def test_api_does_not_expose_inference_endpoints() -> None:
    response = client.get("/openapi.json")
    schema = response.json()

    paths = list(schema["paths"].keys())

    forbidden_paths = [
        "/inference",
        "/infer",
        "/classify",
        "/predict",
        "/upload",
    ]

    for forbidden_path in forbidden_paths:
        assert forbidden_path not in paths