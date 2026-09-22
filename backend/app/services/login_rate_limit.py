import hashlib
from typing import Any, cast

from redis import Redis
from redis.exceptions import RedisError

from app.api.errors import api_error
from app.core.config import settings


def enforce_login_rate_limit(client_ip: str, email: str) -> None:
    """Use a non-PII digest and a fixed Redis window shared by all API replicas."""
    identity = f"{client_ip}|{email.strip().lower()}".encode()
    digest = hashlib.sha256(identity).hexdigest()
    key = f"fde:login:{digest}"
    assert settings.REDIS_URL
    client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        value = int(cast(Any, client.incr(key)))
        if value == 1:
            client.expire(key, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS)
    except RedisError:
        api_error(
            503,
            "authentication_unavailable",
            "Authentication is temporarily unavailable",
        )
    if value > settings.LOGIN_RATE_LIMIT_ATTEMPTS:
        api_error(
            429, "login_rate_limited", "Too many sign-in attempts; try again later"
        )
