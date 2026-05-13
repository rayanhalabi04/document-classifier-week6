"""Unit tests for RoleManagementService."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.db.models import RoleAssignment
from app.domain.errors import PermissionDenied
from app.services.role_management import RoleManagementService


@pytest.fixture()
def mock_session():
    return MagicMock()


@pytest.fixture()
def admin_id():
    return uuid.uuid4()


@pytest.fixture()
def target_id():
    return uuid.uuid4()


@pytest.fixture()
def mock_authz_admin():
    authz = MagicMock()
    authz.require_permission.return_value = None
    return authz


@pytest.fixture()
def mock_authz_non_admin():
    authz = MagicMock()
    authz.require_permission.side_effect = PermissionDenied("not admin")
    return authz


@pytest.fixture()
def existing_role(target_id):
    role = MagicMock(spec=RoleAssignment)
    role.id = uuid.uuid4()
    role.user_id = target_id
    role.role = "reviewer"
    role.revoked_at = None
    return role


def _patch_authz(authz_mock):
    return patch(
        "app.services.role_management.AuthorizationService", return_value=authz_mock
    )


def _patch_casbin():
    return patch("app.services.role_management.casbin_enforcer")


class TestAssignRole:
    def test_raises_permission_denied_for_non_admin(
        self, mock_session, target_id, admin_id, mock_authz_non_admin
    ):
        with _patch_authz(mock_authz_non_admin), _patch_casbin():
            svc = RoleManagementService(mock_session)
            with pytest.raises(PermissionDenied):
                svc.assign_role(target_id, "reviewer", admin_id)

    def test_raises_value_error_for_invalid_role(
        self, mock_session, target_id, admin_id, mock_authz_admin
    ):
        with _patch_authz(mock_authz_admin), _patch_casbin():
            svc = RoleManagementService(mock_session)
            with pytest.raises(ValueError, match="not a valid role"):
                svc.assign_role(target_id, "superuser", admin_id)

    def test_returns_none_when_role_already_active(
        self, mock_session, target_id, admin_id, mock_authz_admin
    ):
        with (
            _patch_authz(mock_authz_admin),
            _patch_casbin(),
            patch(
                "app.repositories.roles.RoleRepository.has_active_role",
                return_value=True,
            ),
        ):
            svc = RoleManagementService(mock_session)
            result = svc.assign_role(target_id, "reviewer", admin_id)

        assert result is None
        mock_session.commit.assert_not_called()

    def test_creates_assignment_when_role_not_active(
        self, mock_session, target_id, admin_id, mock_authz_admin
    ):
        with (
            _patch_authz(mock_authz_admin),
            _patch_casbin(),
            patch(
                "app.repositories.roles.RoleRepository.has_active_role",
                return_value=False,
            ),
            patch(
                "app.repositories.roles.RoleRepository.create", side_effect=lambda a: a
            ),
            patch("app.services.cache_invalidation.invalidate_user_roles"),
        ):
            svc = RoleManagementService(mock_session)
            result = svc.assign_role(target_id, "reviewer", admin_id)

        assert result is not None
        assert result.role == "reviewer"
        assert result.user_id == target_id
        mock_session.commit.assert_called_once()


class TestRevokeRole:
    def test_raises_permission_denied_for_non_admin(
        self, mock_session, target_id, admin_id, mock_authz_non_admin
    ):
        with _patch_authz(mock_authz_non_admin), _patch_casbin():
            svc = RoleManagementService(mock_session)
            with pytest.raises(PermissionDenied):
                svc.revoke_role(target_id, "reviewer", admin_id)

    def test_raises_value_error_when_role_not_active(
        self, mock_session, target_id, admin_id, mock_authz_admin
    ):
        with (
            _patch_authz(mock_authz_admin),
            _patch_casbin(),
            patch(
                "app.repositories.roles.RoleRepository.get_active_roles",
                return_value=[],
            ),
        ):
            svc = RoleManagementService(mock_session)
            with pytest.raises(ValueError, match="does not have active role"):
                svc.revoke_role(target_id, "reviewer", admin_id)

    def test_revokes_role_successfully(
        self, mock_session, target_id, admin_id, mock_authz_admin, existing_role
    ):
        with (
            _patch_authz(mock_authz_admin),
            _patch_casbin(),
            patch(
                "app.repositories.roles.RoleRepository.get_active_roles",
                return_value=[existing_role],
            ),
            patch("app.repositories.roles.RoleRepository.revoke"),
            patch("app.services.cache_invalidation.invalidate_user_roles"),
        ):
            svc = RoleManagementService(mock_session)
            svc.revoke_role(target_id, "reviewer", admin_id)

        mock_session.commit.assert_called_once()


class TestReplaceRoles:
    def test_raises_permission_denied_for_non_admin(
        self, mock_session, target_id, admin_id, mock_authz_non_admin
    ):
        with _patch_authz(mock_authz_non_admin), _patch_casbin():
            svc = RoleManagementService(mock_session)
            with pytest.raises(PermissionDenied):
                svc.replace_roles(target_id, ["reviewer"], admin_id)

    def test_raises_value_error_for_invalid_role_in_list(
        self, mock_session, target_id, admin_id, mock_authz_admin
    ):
        with _patch_authz(mock_authz_admin), _patch_casbin():
            svc = RoleManagementService(mock_session)
            with pytest.raises(ValueError):
                svc.replace_roles(target_id, ["reviewer", "god"], admin_id)

    def test_replaces_roles_and_commits(
        self, mock_session, target_id, admin_id, mock_authz_admin
    ):
        new_assignment = MagicMock(spec=RoleAssignment)
        with (
            _patch_authz(mock_authz_admin),
            _patch_casbin(),
            patch("app.repositories.roles.RoleRepository.revoke_all_for_user"),
            patch(
                "app.repositories.roles.RoleRepository.create",
                return_value=new_assignment,
            ),
            patch("app.services.cache_invalidation.invalidate_user_roles"),
        ):
            svc = RoleManagementService(mock_session)
            result = svc.replace_roles(target_id, ["auditor"], admin_id)

        assert len(result) == 1
        mock_session.commit.assert_called_once()

    def test_can_strip_all_roles_with_empty_list(
        self, mock_session, target_id, admin_id, mock_authz_admin
    ):
        with (
            _patch_authz(mock_authz_admin),
            _patch_casbin(),
            patch("app.repositories.roles.RoleRepository.revoke_all_for_user"),
            patch("app.services.cache_invalidation.invalidate_user_roles"),
        ):
            svc = RoleManagementService(mock_session)
            result = svc.replace_roles(target_id, [], admin_id)

        assert result == []
        mock_session.commit.assert_called_once()


class TestGetActiveRoles:
    def test_returns_list_of_role_name_strings(
        self, mock_session, target_id, existing_role
    ):
        existing_role.role = "reviewer"
        with patch(
            "app.repositories.roles.RoleRepository.get_active_roles",
            return_value=[existing_role],
        ):
            svc = RoleManagementService(mock_session)
            result = svc.get_active_roles(target_id)

        assert result == ["reviewer"]

    def test_returns_empty_list_when_no_roles(self, mock_session, target_id):
        with patch(
            "app.repositories.roles.RoleRepository.get_active_roles",
            return_value=[],
        ):
            svc = RoleManagementService(mock_session)
            result = svc.get_active_roles(target_id)

        assert result == []
