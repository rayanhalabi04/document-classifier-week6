"""Unit tests for app/services/cache_invalidation.py (T033)."""

import uuid
from unittest.mock import call, patch

import pytest

from app.services.cache_invalidation import (
    ROLES,
    invalidate_after_classification,
    invalidate_after_relabel,
    invalidate_audit_list,
    invalidate_batch_detail,
    invalidate_batch_list,
    invalidate_prediction_detail,
    invalidate_user_roles,
)


@pytest.fixture(autouse=True)
def mock_delete(monkeypatch):
    """Patch the internal _delete so no Redis connection is needed."""
    with patch("app.services.cache_invalidation._delete") as mock:
        yield mock


class TestInvalidateBatchList:
    def test_deletes_key_for_each_role(self, mock_delete):
        invalidate_batch_list()
        assert mock_delete.call_count == len(ROLES)
        for role in ROLES:
            mock_delete.assert_any_call(f"batches:list:{role}")


class TestInvalidateBatchDetail:
    def test_deletes_key_for_each_role(self, mock_delete):
        batch_id = uuid.uuid4()
        invalidate_batch_detail(batch_id)
        assert mock_delete.call_count == len(ROLES)
        for role in ROLES:
            mock_delete.assert_any_call(f"batches:detail:{batch_id}:{role}")


class TestInvalidatePredictionDetail:
    def test_deletes_key_for_each_role(self, mock_delete):
        pred_id = uuid.uuid4()
        invalidate_prediction_detail(pred_id)
        assert mock_delete.call_count == len(ROLES)
        for role in ROLES:
            mock_delete.assert_any_call(f"predictions:detail:{pred_id}:{role}")


class TestInvalidateAuditList:
    def test_deletes_key_for_each_role(self, mock_delete):
        invalidate_audit_list()
        assert mock_delete.call_count == len(ROLES)
        for role in ROLES:
            mock_delete.assert_any_call(f"audit:list:{role}")


class TestInvalidateUserRoles:
    def test_deletes_user_roles_key(self, mock_delete):
        user_id = uuid.uuid4()
        invalidate_user_roles(user_id)
        mock_delete.assert_any_call(f"users:roles:{user_id}")

    def test_also_invalidates_batch_list(self, mock_delete):
        invalidate_user_roles(uuid.uuid4())
        # Should include batch list keys for each role
        for role in ROLES:
            mock_delete.assert_any_call(f"batches:list:{role}")


class TestInvalidateAfterClassification:
    def test_invalidates_batch_list_detail_and_prediction(self, mock_delete):
        batch_id = uuid.uuid4()
        pred_id = uuid.uuid4()
        invalidate_after_classification(batch_id, pred_id)
        # batch list (3) + batch detail (3) + prediction detail (3) = 9
        assert mock_delete.call_count == 3 * len(ROLES)


class TestInvalidateAfterRelabel:
    def test_invalidates_batch_and_prediction_and_audit(self, mock_delete):
        batch_id = uuid.uuid4()
        pred_id = uuid.uuid4()
        invalidate_after_relabel(batch_id, pred_id)
        # batch list + batch detail + prediction detail + audit list = 4 * len(ROLES)
        assert mock_delete.call_count == 4 * len(ROLES)


class TestRedisFailureHandling:
    def test_redis_failure_is_logged_not_raised(self):
        """Cache invalidation failures must not propagate to callers."""
        from app.domain.errors import CacheInvalidationError

        with patch(
            "app.services.cache_invalidation._delete",
            side_effect=CacheInvalidationError("Redis down"),
        ):
            # Should not raise — failures are swallowed and logged
            invalidate_batch_list()
