import pytest

from app.core.database_urls import libpq_url, sqlalchemy_psycopg_url


def test_database_url_conversions_preserve_encoded_credentials_and_options() -> None:
    source = (
        "postgresql+psycopg://service:p%40ss%2Fword@database:5432/app"
        "?sslmode=verify-full"
    )

    assert sqlalchemy_psycopg_url(source, database="restored") == (
        "postgresql+psycopg://service:p%40ss%2Fword@database:5432/restored"
        "?sslmode=verify-full"
    )
    assert libpq_url(source, database="postgres") == (
        "postgresql://service:p%40ss%2Fword@database:5432/postgres?sslmode=verify-full"
    )


def test_database_url_conversions_reject_other_backends() -> None:
    with pytest.raises(ValueError, match="must use PostgreSQL"):
        sqlalchemy_psycopg_url("sqlite:///local.db")


def test_legacy_postgres_scheme_is_normalized_for_each_consumer() -> None:
    source = "postgres://app:secret@database/app"
    assert sqlalchemy_psycopg_url(source).startswith("postgresql+psycopg://")
    assert libpq_url(source).startswith("postgresql://")
