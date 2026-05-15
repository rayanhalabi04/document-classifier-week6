"""Redis 7 connection adapter.

Provides synchronous and asynchronous Redis clients from a single
REDIS_URL environment variable. Synchronous client is used by RQ and
health checks; async client is used by fastapi-cache2.

Clients are cached via lru_cache to avoid creating new connection
pools on every call.
"""

from __future__ import annotations

from functools import lru_cache

import redis.asyncio as aioredis
from redis import Redis

from app.config import settings


def _get_redis_url() -> str:
    return settings.redis_url


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    """Return a synchronous Redis client configured from REDIS_URL.

    Uses binary mode (decode_responses=False) so RQ can store
    pickle-serialised job payloads without corruption.
    """
    return Redis.from_url(_get_redis_url(), decode_responses=False)


@lru_cache(maxsize=1)
def get_async_redis_client() -> aioredis.Redis:
    """Return an async Redis client configured from REDIS_URL.

    Uses string mode (decode_responses=True) as required by
    fastapi-cache2 RedisBackend.
    """
    return aioredis.Redis.from_url(_get_redis_url(), decode_responses=True)


def check_redis_health() -> None:
    """Ping Redis synchronously.

    Raises redis.exceptions.ConnectionError on failure.
    """
    get_redis_client().ping()
