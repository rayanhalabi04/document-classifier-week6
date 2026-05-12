"""Redis 7 connection adapter.

Note: The full adapter implementation is Member 4's domain (T031).
This module provides the minimal interface needed by startup validation.
Member 4 may replace/enhance this with their full adapter.
"""

from __future__ import annotations

import os

from redis import Redis


def get_redis_client() -> Redis:
    """Return a Redis client configured from environment.

    Called by startup validation health checks.
    """
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    return Redis.from_url(redis_url)
