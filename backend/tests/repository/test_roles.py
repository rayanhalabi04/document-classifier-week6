"""Unit tests for RoleRepository."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.db.models import RoleAssignment
from app.repositories.roles import RoleRepository


@pytest.fixture()
def active_role(user_id):
    role = MagicMock(spec=RoleAssignment)
    role.id = uuid.uuid4()
    role.user_id = user_id
    role.role = "reviewer"
    role.revoked_at = None
    return role


class TestGetActiveRoles:
    def test_returns_active_roles_for_user(self, mock_session, active_role, user_id):
        mock_session.execute.return_value.scalars.return_value.all.return_value = [active_role]
        repo = RoleRepository(mock_session)

        result = repo.get_active_roles(user_id)

        assert result == [active_role]

    def test_returns_empty_when_no_active_roles(self, mock_session, user_id):
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        repo = RoleRepository(mock_session)

        result = repo.get_active_roles(user_id)

        assert result == []


class TestHasActiveRole:
    def test_returns_true_when_role_exists(self, mock_session, active_role, user_id):
        mock_session.execute.return_value.scalar_one_or_none.return_value = active_role
        repo = RoleRepository(mock_session)

        result = repo.has_active_role(user_id, "reviewer")

        assert result is True

    def test_returns_false_when_role_not_found(self, mock_session, user_id):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        repo = RoleRepository(mock_session)

        result = repo.has_active_role(user_id, "admin")

        assert result is False


class TestGetById:
    def test_returns_role_when_found(self, mock_session, active_role):
        mock_session.execute.return_value.scalar_one_or_none.return_value = active_role
        repo = RoleRepository(mock_session)

        result = repo.get_by_id(active_role.id)

        assert result is active_role

    def test_returns_none_when_not_found(self, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        repo = RoleRepository(mock_session)

        result = repo.get_by_id(uuid.uuid4())

        assert result is None


class TestCreate:
    def test_adds_role_to_session_and_flushes(self, mock_session):
        role = MagicMock(spec=RoleAssignment)
        repo = RoleRepository(mock_session)

        result = repo.create(role)

        mock_session.add.assert_called_once_with(role)
        mock_session.flush.assert_called_once()
        assert result is role


class TestRevoke:
    def test_sets_revoked_at_and_flushes(self, mock_session, active_role):
        mock_session.execute.return_value.scalar_one_or_none.return_value = active_role
        repo = RoleRepository(mock_session)

        result = repo.revoke(active_role.id)

        assert active_role.revoked_at is not None
        mock_session.flush.assert_called_once()
        assert result is active_role

    def test_returns_none_when_role_not_found(self, mock_session):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        repo = RoleRepository(mock_session)

        result = repo.revoke(uuid.uuid4())

        assert result is None

    def test_uses_provided_revoked_at_timestamp(self, mock_session, active_role):
        mock_session.execute.return_value.scalar_one_or_none.return_value = active_role
        repo = RoleRepository(mock_session)
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)

        repo.revoke(active_role.id, revoked_at=ts)

        assert active_role.revoked_at == ts


class TestRevokeAllForUser:
    def test_sets_revoked_at_on_all_active_roles(self, mock_session, active_role, user_id):
        role2 = MagicMock(spec=RoleAssignment)
        role2.revoked_at = None
        mock_session.execute.return_value.scalars.return_value.all.return_value = [
            active_role,
            role2,
        ]
        repo = RoleRepository(mock_session)

        repo.revoke_all_for_user(user_id)

        assert active_role.revoked_at is not None
        assert role2.revoked_at is not None
        mock_session.flush.assert_called_once()

    def test_no_op_when_no_active_roles(self, mock_session, user_id):
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        repo = RoleRepository(mock_session)

        repo.revoke_all_for_user(user_id)

        mock_session.flush.assert_called_once()
