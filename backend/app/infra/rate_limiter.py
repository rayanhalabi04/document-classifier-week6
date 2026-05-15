"""Redis-backed rate limiter for auth endpoints.

Uses a fixed-window counter per client IP.  Returns 429 Too Many Requests
when the limit is exceeded.
"""

from __future__ import annotations

import time

from fastapi import Request
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError

from app.infra.redis import get_redis_client

_AUTH_RATE_LIMIT = 10
_AUTH_RATE_WINDOW_SECONDS = 60


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client else "unknown"


async def auth_rate_limit_middleware(request: Request, call_next):
    """Block requests to /auth/* if rate limit exceeded."""
    if not request.url.path.startswith("/auth"):
        return await call_next(request)

    ip = _client_ip(request)
    key = f"ratelimit:auth:{ip}"
    window = int(time.time() // _AUTH_RATE_WINDOW_SECONDS)
    full_key = f"{key}:{window}"

    try:
        client = get_redis_client()
        count = client.incr(full_key)
        if count == 1:
            client.expire(full_key, _AUTH_RATE_WINDOW_SECONDS + 1)
        if count > _AUTH_RATE_LIMIT:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Try again later.",
                    "retry_after_seconds": _AUTH_RATE_WINDOW_SECONDS,
                },
            )
    except RedisError:
        pass  # fail open — don't block auth if Redis is down

    return await call_next(request)
