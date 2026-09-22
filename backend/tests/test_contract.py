from app.main import app


def test_openapi_exposes_managed_identity_and_import_contract() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    assert "/api/v1/users/signup" not in paths
    assert "/api/v1/password-recovery/{email}" not in paths
    assert "/api/v1/imports" in paths
    assert "/api/v1/imports/{import_id}/confirm" in paths
    assert "/api/v1/imports/{import_id}/reports/{report_name}" in paths
    assert "/internal/metrics" not in paths


def test_confirmation_requires_idempotency_header() -> None:
    operation = app.openapi()["paths"]["/api/v1/imports/{import_id}/confirm"]["post"]
    parameters = {item["name"]: item for item in operation["parameters"]}
    assert parameters["Idempotency-Key"]["required"] is True
