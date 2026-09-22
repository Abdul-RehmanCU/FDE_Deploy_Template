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
