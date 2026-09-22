from pathlib import Path

from fastapi import APIRouter, Response
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text

from app.api.deps import SessionDep
from app.core.config import settings
from app.models import HealthPublic, VersionPublic

router = APIRouter(tags=["operations"])


@router.get("/health/live", response_model=HealthPublic)
def liveness() -> HealthPublic:
    return HealthPublic(status="ok")


@router.get("/health/ready", response_model=HealthPublic)
def readiness(session: SessionDep, response: Response) -> HealthPublic:
    failures: list[str] = []
    try:
        session.execute(text("SELECT 1"))
    except Exception:
        failures.append("database")
    try:
        assert settings.REDIS_URL
        Redis.from_url(
            settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2
        ).ping()
    except (RedisError, AssertionError):
        failures.append("redis")
    if settings.STORAGE_BACKEND == "local":
        try:
            Path(settings.STORAGE_LOCAL_ROOT).mkdir(parents=True, exist_ok=True)
        except OSError:
            failures.append("storage")
    if failures:
        response.status_code = 503
        return HealthPublic(status="unavailable")
    return HealthPublic(status="ok")


@router.get("/version", response_model=VersionPublic)
def version() -> VersionPublic:
    return VersionPublic(
        version=settings.APP_VERSION, environment=settings.APP_ENVIRONMENT
    )
