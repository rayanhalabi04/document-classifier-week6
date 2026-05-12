"""fastapi-cache2 Redis backend setup and synchronous cache key deletion.

init_cache() is called once during FastAPI lifespan startup.
delete_cache_key() is called synchronously by cache_invalidation.py
after successful Postgres commits.
"""

from __future__ import annotations

import logging

from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend

from app.infra.redis import get_async_redis_client, get_redis_client

logger = logging.getLogger(__name__)

CACHE_PREFIX = "fastapi-cache"


async def init_cache() -> None:
    """Initialise the fastapi-cache2 Redis backend.

    Call once from the FastAPI lifespan context manager after the event
    loop is running. Uses the async Redis client required by RedisBackend.
    """
    async_client = get_async_redis_client()
    FastAPICache.init(RedisBackend(async_client), prefix=CACHE_PREFIX)
    logger.info("fastapi-cache2 Redis backend initialised")


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
    full_key = f"{CACHE_PREFIX}:{key}"
    get_redis_client().delete(full_key)
