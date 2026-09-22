from fastapi.testclient import TestClient

from app.main import app


def test_validation_errors_do_not_echo_secret_input() -> None:
    secret_input = "short-secret-value"
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/login/access-token",
            data={"username": "not-an-email", "password": secret_input},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    assert response.status_code in (400, 503)
    assert secret_input not in response.text


def test_missing_token_uses_stable_safe_error_envelope() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/contacts")
    assert response.status_code == 401
    assert response.json() == {
        "detail": {"code": "invalid_token", "message": "Authentication is required"}
    }
