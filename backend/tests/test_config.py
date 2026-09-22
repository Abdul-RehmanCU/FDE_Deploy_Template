from pathlib import Path

from app.core.config import Settings


def test_secret_files_take_precedence(tmp_path: Path) -> None:
    secret_file = tmp_path / "secret"
    database_file = tmp_path / "database"
    redis_file = tmp_path / "redis"
    secret_file.write_text("f" * 40)
    database_file.write_text("postgresql://file:file@db/app")
    redis_file.write_text("redis://redis:6379/0")
    configured = Settings(
        _env_file=None,
        SECRET_KEY="d" * 40,
        SECRET_KEY_FILE=secret_file,
        DATABASE_URL="postgresql://direct:direct@db/app",
        DATABASE_URL_FILE=database_file,
        REDIS_URL="redis://direct:6379/0",
        REDIS_URL_FILE=redis_file,
    )
    assert configured.SECRET_KEY == "f" * 40
    assert configured.DATABASE_URL == "postgresql://file:file@db/app"
    assert configured.REDIS_URL == "redis://redis:6379/0"
    assert configured.sqlalchemy_database_url == "postgresql+psycopg://file:file@db/app"


def test_verified_database_and_redis_tls_files_become_connection_options(
    tmp_path: Path,
) -> None:
    ca = tmp_path / "ca.pem"
    cert = tmp_path / "client.pem"
    key = tmp_path / "client.key"
    for path in (ca, cert, key):
        path.write_text("test-certificate-material")
    configured = Settings(
        _env_file=None,
        SECRET_KEY="s" * 40,
        DATABASE_URL="postgresql://app:secret@database/app",
        DATABASE_SSLMODE="verify-ca",
        DATABASE_SSLROOTCERT_FILE=ca,
        DATABASE_SSLCERT_FILE=cert,
        DATABASE_SSLKEY_FILE=key,
        REDIS_URL="rediss://:secret@redis:6378/0",
        REDIS_CA_FILE=ca,
    )
    assert configured.database_connect_args == {
        "sslmode": "verify-ca",
        "sslrootcert": str(ca),
        "sslcert": str(cert),
        "sslkey": str(key),
    }
    assert configured.redis_connection_kwargs == {
        "ssl_ca_certs": str(ca),
        "ssl_cert_reqs": "required",
        "ssl_check_hostname": True,
    }
    assert configured.celery_broker_use_ssl
    assert configured.celery_broker_use_ssl["ssl_ca_certs"] == str(ca)
    assert configured.celery_broker_use_ssl["ssl_check_hostname"] is True


def test_rediss_refuses_missing_trust_anchor() -> None:
    try:
        Settings(
            _env_file=None,
            SECRET_KEY="s" * 40,
            DATABASE_URL="postgresql://app:secret@database/app",
            REDIS_URL="rediss://:secret@redis:6378/0",
        )
    except ValueError as exc:
        assert "REDIS_CA_FILE" in str(exc)
    else:
        raise AssertionError("rediss:// must fail closed without a CA file")
