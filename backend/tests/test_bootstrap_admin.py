import pytest
import typer

from app.bootstrap_admin import validate_admin_email


def test_gke_smoke_identity_pattern_passes_bootstrap_validation() -> None:
    email = "smoke-35707717123-production-demo@example.com"
    assert validate_admin_email(email) == email


def test_reserved_invalid_domain_fails_bootstrap_validation() -> None:
    with pytest.raises(typer.BadParameter, match="valid email"):
        validate_admin_email("smoke-35707717123-staging@example.invalid")
