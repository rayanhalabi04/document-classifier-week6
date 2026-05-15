"""fastapi-cache2 Redis backend setup and synchronous cache key deletion.

init_cache() is called once during FastAPI lifespan startup.
delete_cache_key() is called synchronously by cache_invalidation.py
after successful Postgres commits.
"""

from __future__ import annotations

from app.infra.logging import get_logger

from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis.exceptions import RedisError

from app.config import settings
from app.infra.redis import get_async_redis_client, get_redis_client

logger = get_logger(__name__)


async def init_cache() -> None:
    """Initialise the fastapi-cache2 Redis backend.

    Call once from the FastAPI lifespan context manager after the event
    loop is running.  Fails gracefully — if Redis is unreachable the API
    starts without cache protection and every @cache decorator degrades
    to a pass-through (cache miss, DB hit).
    """
    try:
        async_client = get_async_redis_client()
        FastAPICache.init(
            RedisBackend(async_client),
            prefix=settings.cache_prefix,
            expire=settings.cache_default_ttl,
        )
        logger.info("fastapi-cache2 Redis backend initialised")
    except RedisError:
        logger.warning(
            "Redis unreachable — cache disabled. API will serve without cache."
        )


def delete_cache_key(key: str) -> None:
    """Delete a single cache key from Redis synchronously.

    Uses the synchronous Redis client so cache_invalidation.py can call
    this from synchronous service code without requiring an event loop.

    The full Redis key is "<CACHE_PREFIX>:<key>".

    Args:
        key: Logical cache key without prefix, e.g. "batches:list:admin".

    Raises:
        redis.exceptions.RedisError: On Redis communication failure.
            cache_invalidation.py wraps this in CacheInvalidationError.
    """
    full_key = f"{settings.cache_prefix}:{key}"
    get_redis_client().delete(full_key)
