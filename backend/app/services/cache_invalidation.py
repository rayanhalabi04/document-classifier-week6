"""Cache invalidation service.

Services call this after a successful commit. Routers never invalidate directly.
Redis deletion failures are logged and audited but do not roll back Postgres data.
"""

from app.infra.logging import get_logger
import uuid

from app.domain.errors import CacheInvalidationError

logger = get_logger(__name__)

# RVL-CDIP role identifiers used in cache key scoping
ROLES = ("admin", "reviewer", "auditor")


def _delete(key: str) -> None:
    """Delete one key from the Redis cache backend.

    Import is deferred to avoid circular imports with infra layer.
    Raises CacheInvalidationError on Redis failure.
    """
    try:
        from app.infra.cache import delete_cache_key

        delete_cache_key(key)
    except Exception as exc:
        raise CacheInvalidationError(f"Failed to delete cache key '{key}'") from exc


def _try_delete(key: str) -> None:
    """Delete a cache key, logging failures without raising."""
    try:
        _delete(key)
    except CacheInvalidationError:
        logger.warning("Cache invalidation failed for key '%s'", key)


def invalidate_batch_list() -> None:
    """Invalidate batch list cache for all roles."""
    for role in ROLES:
        _try_delete(f"batches:list:{role}")


def invalidate_batch_detail(batch_id: uuid.UUID) -> None:
    """Invalidate batch detail cache for all roles."""
    for role in ROLES:
        _try_delete(f"batches:detail:{batch_id}:{role}")


def invalidate_prediction_detail(prediction_id: uuid.UUID) -> None:
    """Invalidate prediction detail cache for all roles."""
    for role in ROLES:
        _try_delete(f"predictions:detail:{prediction_id}:{role}")


def invalidate_audit_list() -> None:
    """Invalidate audit event list cache for all roles."""
    for role in ROLES:
        _try_delete(f"audit:list:{role}")


def invalidate_user_roles(user_id: uuid.UUID) -> None:
    """Invalidate user role cache and all role-scoped keys for the affected user."""
    _try_delete(f"users:roles:{user_id}")
    # Role change affects all role-scoped views for this user
    invalidate_batch_list()


def invalidate_after_classification(
    batch_id: uuid.UUID,
    prediction_id: uuid.UUID,
) -> None:
    """Invalidate all caches affected by a new classification result."""
    invalidate_batch_list()
    invalidate_batch_detail(batch_id)
    invalidate_prediction_detail(prediction_id)


def invalidate_after_relabel(
    batch_id: uuid.UUID,
    prediction_id: uuid.UUID,
) -> None:
    """Invalidate all caches affected by a reviewer relabel."""
    invalidate_batch_list()
    invalidate_batch_detail(batch_id)
    invalidate_prediction_detail(prediction_id)
    invalidate_audit_list()
