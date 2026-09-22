from pathlib import Path
from typing import Literal, Self

from pydantic import HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_ignore_empty=True, extra="ignore"
    )

    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "FDE Deployment Template"
    APP_ENVIRONMENT: str = "development"
    APP_VERSION: str = "dev"
    FASTAPI_ENV: Literal["development", "test", "production"] = "development"

    SECRET_KEY: str | None = None
    SECRET_KEY_FILE: Path | None = None
    DATABASE_URL: str | None = None
    DATABASE_URL_FILE: Path | None = None
    REDIS_URL: str | None = None
    REDIS_URL_FILE: Path | None = None

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    BACKEND_CORS_ORIGINS: list[str] | str = ["http://localhost:5173"]
    LOGIN_RATE_LIMIT_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 60
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT_SECONDS: int = 10
    DB_STATEMENT_TIMEOUT_MS: int = 30_000

    STORAGE_BACKEND: Literal["local", "gcs"] = "local"
    STORAGE_LOCAL_ROOT: Path = Path(".data/storage")
    GCS_BUCKET: str | None = None
    UPLOAD_MAX_BYTES: int = 10 * 1024 * 1024
    UPLOAD_MAX_ROWS: int = 10_000
    INTERMEDIATE_RETENTION_DAYS: int = 7

    CELERY_TASK_MAX_RETRIES: int = 3
    CELERY_TASK_TIME_LIMIT_SECONDS: int = 600
    OUTBOX_POLL_SECONDS: float = 1.0
    OUTBOX_PUBLISH_TIMEOUT_SECONDS: int = 10
    JOB_STALE_SECONDS: int = 900
    JOB_RECONCILE_INTERVAL_SECONDS: int = 30
    WORKER_METRICS_PORT: int = 9100
    SENTRY_DSN: HttpUrl | None = None
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None
    OTEL_SERVICE_NAME: str = "fde-api"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @staticmethod
    def _read_secret(path: Path | None, name: str) -> str | None:
        if path is None:
            return None
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError(f"Unable to read {name} secret file") from exc
        if not value:
            raise ValueError(f"{name} secret file is empty")
        return value

    @model_validator(mode="after")
    def resolve_and_validate_secrets(self) -> Self:
        self.SECRET_KEY = (
            self._read_secret(self.SECRET_KEY_FILE, "SECRET_KEY") or self.SECRET_KEY
        )
        self.DATABASE_URL = (
            self._read_secret(self.DATABASE_URL_FILE, "DATABASE_URL")
            or self.DATABASE_URL
        )
        self.REDIS_URL = (
            self._read_secret(self.REDIS_URL_FILE, "REDIS_URL") or self.REDIS_URL
        )
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY or SECRET_KEY_FILE is required")
        if len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must contain at least 32 characters")
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL or DATABASE_URL_FILE is required")
        if not self.REDIS_URL:
            raise ValueError("REDIS_URL or REDIS_URL_FILE is required")
        if self.STORAGE_BACKEND == "gcs" and not self.GCS_BUCKET:
            raise ValueError("GCS_BUCKET is required when STORAGE_BACKEND=gcs")
        if self.FASTAPI_ENV != "development" and self.SECRET_KEY.startswith(
            "generate-"
        ):
            raise ValueError("Placeholder secrets are forbidden outside development")
        return self

    @property
    def sqlalchemy_database_url(self) -> str:
        assert self.DATABASE_URL
        value = self.DATABASE_URL
        for scheme in ("postgres://", "postgresql://"):
            if value.startswith(scheme):
                return value.replace(scheme, "postgresql+psycopg://", 1)
        return value


settings = Settings()  # type: ignore[call-arg]
